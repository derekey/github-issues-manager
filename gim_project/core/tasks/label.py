
from limpyd import fields

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
        Get the label and create or update it
        """
        super(LabelEditJob, self).run(queue)

        self.object.dist_edit(
            mode=self.mode.hget(),
            gh=self.gh
        )

        return None

    def success_message_addon(self, queue, result):
        """
        Display the action done (updated or created)
        """
        return ' [%sd]' % self.mode.hget()
