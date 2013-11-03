
from limpyd import fields
from async_messages import messages

from core.models import Label
from core.ghpool import ApiError

from . import DjangoModelJob


class LabelJob(DjangoModelJob):
    """
    Abstract job model for jobs based on the Label model
    """
    abstract = True
    model = Label


class LabelEditJob(LabelJob):

    queue_name = 'edit-label'

    mode = fields.InstanceHashField()

    def run(self, queue):
        """
        Get the label and create/update/delete it
        """
        super(LabelEditJob, self).run(queue)

        mode = self.mode.hget()
        gh = self.gh

        try:
            label = self.object
        except Label.DoesNotExist:
            return None

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

