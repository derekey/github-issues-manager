__all__ = []

from datetime import timedelta

from django.db import models
from django.db.models.signals import post_save

from core.models import (Repository, Issue, IssueComment, IssueEvent,
                         PullRequestComment, Commit)
from core.utils import contribute_to_model

from events.models import Event, EventPart

from .managers import ActivityManager


class _Repository(models.Model):
    class Meta:
        abstract = True

    @property
    def activity(self):
        from .limpyd_models import RepositoryActivity
        a, created = RepositoryActivity.get_or_connect(object_id=self.id)
        return a

contribute_to_model(_Repository, Repository)


class _Issue(models.Model):
    class Meta:
        abstract = True

    @property
    def activity(self):
        from .limpyd_models import IssueActivity
        a, created = IssueActivity.get_or_connect(object_id=self.id)
        return a

    def ask_for_activity_update(self):
        from .tasks import ResetIssueActivity
        ResetIssueActivity.add_job(self.pk, priority=-5, delayed_for=timedelta(minutes=15))

contribute_to_model(_Issue, Issue)


def update_activity_for_m2m_link(sender, instance, created, **kwargs):
    # only if the object can be saved in the activity stream
    manager = ActivityManager.get_for_model_instance(instance)
    for issue in instance.issues.all():
        if not manager.is_obj_valid(issue, instance):
            return
        issue.activity.add_entry(instance)
        issue.ask_for_activity_update()

post_save.connect(update_activity_for_m2m_link, sender=Commit, weak=False,
                  dispatch_uid='update_activity_for_m2m_link_Commit')


def update_activity_for_fk_link(sender, instance, created, **kwargs):
    if not instance.issue_id:
        return
    # only if the object can be saved in the activity stream
    manager = ActivityManager.get_for_model_instance(instance)
    if not manager.is_obj_valid(instance.issue, instance):
        return
    instance.issue.activity.add_entry(instance)
    instance.issue.ask_for_activity_update()

post_save.connect(update_activity_for_fk_link, sender=IssueComment, weak=False,
                  dispatch_uid='update_activity_for_fk_link_IssueComment')
post_save.connect(update_activity_for_fk_link, sender=IssueEvent, weak=False,
                  dispatch_uid='update_activity_for_fk_link_IssueEvent')
post_save.connect(update_activity_for_fk_link, sender=PullRequestComment, weak=False,
                  dispatch_uid='update_activity_for_fk_link_PullRequestComment')
post_save.connect(update_activity_for_fk_link, sender=Event, weak=False,
                  dispatch_uid='update_activity_for_fk_link_Event')


def update_activity_for_event_part(sender, instance, created, **kwargs):
    if not instance.issue_id:
        return
    # first check for fields we want to ignore
    if instance.field in Issue.RENDERER_IGNORE_FIELDS and instance.event.is_update:
        return
    # only if the event can be saved in the activity stream
    manager = ActivityManager.get_for_model_instance(instance)
    if not manager.is_obj_valid(instance.issue, instance):
        return
    instance.event.issue.activity.add_entry(instance.event)
    instance.event.issue.ask_for_activity_update()

post_save.connect(update_activity_for_fk_link, sender=EventPart, weak=False,
                  dispatch_uid='update_activity_for_event_part')
