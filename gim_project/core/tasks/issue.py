import time

from limpyd import fields

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
