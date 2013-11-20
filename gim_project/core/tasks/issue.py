import time

from limpyd import fields
from async_messages import messages

from core.models import Issue, Repository
from core.ghpool import ApiError

from . import DjangoModelJob, Job


class FetchIssueByNumber(Job):
    """
    Fetch the whole issue for a repository, given only the issue's number
    """
    queue_name = 'fetch-issue-by-number'

    def run(self, queue):
        """
        Fetch the issue with the given number for the current repository
        """
        super(FetchIssueByNumber, self).run(queue)

        repository_id, issue_number = self.identifier.hget().split('#')

        repository = Repository.objects.get(id=repository_id)

        try:
            gh = self.gh
        except Exception:
            gh = repository.get_gh()

        try:
            issue = repository.issues.get(number=issue_number)
        except Issue.DoesNotExist:
            issue = Issue(repository=repository, number=issue_number)

        issue.fetch_all(gh)


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

        issue = self.object

        try:
            issue.dist_edit(mode='update', gh=gh, fields=['state'])
        except ApiError, e:
            message = None
            issue_state_verb = 'close' if issue.state == 'closed' else 'reopen'

            if e.code == 422:
                message = u'Github refused to %s the %s <strong>#%s</strong> on <strong>%s</strong>' % (
                    issue_state_verb, issue.type, issue.number, issue.repository.full_name)

            elif e.code in (401, 403):
                tries = self.tries.hget()
                if tries and int(tries) >= 5:
                    message = u'You seem to not have the right to %s the %s <strong>#%s</strong> on <strong>%s</strong>' % (
                        issue_state_verb, issue.type, issue.number, issue.repository.full_name)

            if message:
                messages.error(self.gh_user, message)
                try:
                    self.object.fetch(gh, force_fetch=True)
                except Exception:
                    pass
                return None

            else:
                raise

        message = u'The %s <strong>#%d</strong> on <strong>%s</strong> was correctly %s' % (
                    issue.type,
                    issue.number,
                    issue.repository.full_name,
                    'closed' if issue.state == 'closed' else 'reopened')
        messages.success(self.gh_user, message)

        self.object.fetch_all(gh)

        return None
