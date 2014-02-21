__all__ = [
    'LabelEditJob',
]

from async_messages import messages

from limpyd import fields
from limpyd_jobs import STATUSES

from core.models import Label
from core.ghpool import ApiError

from .base import DjangoModelJob


class LabelJob(DjangoModelJob):
    """
    Abstract job model for jobs based on the Label model
    """
    abstract = True
    model = Label

    @property
    def label(self):
        if not hasattr(self, '_label'):
            self._label = self.object
        return self._label

    @property
    def repository(self):
        if not hasattr(self, '_repository'):
            self._repository = self.label.repository
        return self._repository


class LabelEditJob(LabelJob):

    queue_name = 'edit-label'

    mode = fields.InstanceHashField()

    permission = 'self'

    def run(self, queue):
        """
        Get the label and create/update/delete it
        """
        super(LabelEditJob, self).run(queue)

        try:
            label = self.label
        except Label.DoesNotExist:
            # the label doesn't exist anymore, stop here
            self.status.hset(STATUSES.CANCELED)
            return None

        gh = self.gh
        if not gh:
            return  # it's delayed !

        mode = self.mode.hget()

        try:
            if mode == 'delete':
                label.dist_delete(gh)
            else:
                label.dist_edit(mode=mode, gh=gh)

        except ApiError, e:
            message = None

            if e.code == 422:
                message = u'Github refused to %s the label <strong>%s</strong> on <strong>%s</strong>' % (
                                mode, label.name, label.repository.full_name)

            elif e.code in (401, 403):
                tries = self.tries.hget()
                if tries and int(tries) >= 5:
                    message = u'You seem to not have the right to %s the label <strong>%s</strong> on <strong>%s</strong>' % (
                            mode, label.name, label.repository.full_name)

            if message:
                messages.error(self.gh_user, message)
                if mode == 'create':
                    label.delete()
                else:
                    try:
                        label.fetch(gh, force_fetch=True)
                    except ApiError:
                        pass
                return None

            else:
                raise

        message = u'The label <strong>%s</strong> was correctly %sd on <strong>%s</strong>' % (
                                label.name, mode, label.repository.full_name)
        messages.success(self.gh_user, message)

        return None

    def success_message_addon(self, queue, result):
        """
        Display the action done (created/updated/deleted)
        """
        return ' [%sd]' % self.mode.hget()
