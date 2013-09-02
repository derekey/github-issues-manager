
from limpyd import fields
from async_messages import messages

from core.models import Label

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

        if mode == 'delete':
            self.object.dist_delete(gh)
        else:
            self.object.dist_edit(mode=mode, gh=gh)

        message = u'The label "%s" was correctly %sd' % (self.object.name, mode)
        messages.success(self.gh_user, message)

        return None

    def success_message_addon(self, queue, result):
        """
        Display the action done (created/updated/deleted)
        """
        return ' [%sd]' % self.mode.hget()
