import time

from limpyd import fields
from async_messages import messages

from core.models import Issue

from . import DjangoModelJob


class IssueJob(DjangoModelJob):
    """
    Abstract job model for jobs based on the Issue model
    """
    abstract = True
    model = Issue


class UpdateIssueCacheTemplate(IssueJob):
    """
    Job that update the cached template of an issue
    """
    queue_name = 'update-issue-tmpl'

    force_regenerate = fields.InstanceHashField()
    update_duration = fields.InstanceHashField()

    def run(self, queue):
        """
        Update the cached template of the issue and save the spent duration
        """
        super(UpdateIssueCacheTemplate, self).run(queue)

        start_time = time.time()

        self.object.update_saved_hash()
        self.object.update_cached_template(
                                force_regenerate=self.force_regenerate.hget())

        duration = '%.2f' % ((time.time() - start_time) * 1000)

        self.update_duration.hset(duration)

        return duration

    def success_message_addon(self, queue, result):
        """
        Display the duration of the cached template update
        """
        duration = self.update_duration.hget()
        if self.force_regenerate.hget():
            return ' [forced=True, duration=%sms]' % duration
        else:
            return ' [duration=%sms]' % duration


class IssueEditStateJob(IssueJob):

    queue_name = 'edit-issue-state'

    def run(self, queue):
        """
        Get the issue and update its state
        """
        super(IssueEditStateJob, self).run(queue)

        gh = self.gh

        self.object.dist_edit(mode='update', gh=gh, fields=['state'])

        message = u'The %s <strong>#%d</strong> was correctly %s' % (
                    'pull request' if self.object.is_pull_request else 'issue',
                    self.object.number,
                    'closed' if self.object.state == 'closed' else 'reopened')
        messages.success(self.gh_user, message)

        self.object.fetch_events(gh, force_fetch=True)

        return None
