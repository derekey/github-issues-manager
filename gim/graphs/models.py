from datetime import timedelta

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from gim.core.models import Repository, Issue
from gim.core.utils import contribute_to_model


class _Repository(models.Model):
    class Meta:
        abstract = True

    @property
    def graphs(self):
        if not hasattr(self, '_graphs_limpyd_object'):
            from .limpyd_models import GraphData
            self._graphs_limpyd_object, created = GraphData.get_or_connect(repository_id=self.id)
        return self._graphs_limpyd_object

contribute_to_model(_Repository, Repository)


@receiver(post_save, sender=Issue, dispatch_uid="update_graphs_data")
def update_graphs_data(sender, instance, created, **kwargs):
    if not isinstance(instance, Issue):
        return
    from gim.graphs.tasks import UpdateGraphsData
    UpdateGraphsData.add_job(instance.repository_id, delayed_for=timedelta(minutes=15))


from gim.graphs.tasks import *
