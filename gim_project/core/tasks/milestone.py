__all__ = [
    'MilestoneEditJob',
]

from async_messages import messages

from limpyd import fields
from limpyd_jobs import STATUSES

from core.models import Milestone
from core.ghpool import ApiError

from .base import DjangoModelJob


class MilestoneJob(DjangoModelJob):
    """
    Abstract job model for jobs based on the Milestone model
    """
    abstract = True
    model = Milestone

    @property
    def milestone(self):
        if not hasattr(self, '_milestone'):
            self._milestone = self.object
        return self._milestone

    @property
    def repository(self):
        if not hasattr(self, '_repository'):
            self._repository = self.milestone.repository
        return self._repository


class MilestoneEditJob(MilestoneJob):

    queue_name = 'edit-milestone'

    mode = fields.InstanceHashField()

    permission = 'self'

    def run(self, queue):
        """
        Get the milestone and create/update/delete it
        """
        super(MilestoneEditJob, self).run(queue)

        try:
            milestone = self.milestone
        except milestone.DoesNotExist:
            # the milestone doesn't exist anymore, stop here
            self.status.hset(STATUSES.CANCELED)
            return None

        gh = self.gh
        if not gh:
            return  # it's delayed !

        mode = self.mode.hget()

        try:
            if mode == 'delete':
                milestone.dist_delete(gh)
            else:
                milestone.dist_edit(mode=mode, gh=gh)

        except ApiError, e:
            message = None

            if e.code == 422:
                message = u'Github refused to %s the milestone <strong>%s</strong> on <strong>%s</strong>' % (
                                mode, milestone.short_title, milestone.repository.full_name)

            elif e.code in (401, 403):
                tries = self.tries.hget()
                if tries and int(tries) >= 5:
                    message = u'You seem to not have the right to %s the milestone <strong>%s</strong> on <strong>%s</strong>' % (
                            mode, milestone.short_title, milestone.repository.full_name)

            if message:
                messages.error(self.gh_user, message)
                if mode == 'create':
                    milestone.delete()
                else:
                    try:
                        milestone.fetch(gh, force_fetch=True)
                    except ApiError:
                        pass
                return None

            else:
                raise

        message = u'The milestone <strong>%s</strong> was correctly %sd on <strong>%s</strong>' % (
                                milestone.short_title, mode, milestone.repository.full_name)
        messages.success(self.gh_user, message)

        return None

    def success_message_addon(self, queue, result):
        """
        Display the action done (created/updated/deleted)
        """
        return ' [%sd]' % self.mode.hget()
