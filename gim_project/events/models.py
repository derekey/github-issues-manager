from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.db import models

from jsonfield import JSONField

from core.models import Repository, Issue

from .renderers import IssueRenderer
from .trackers import *


class Event(models.Model):
    repository = models.ForeignKey(Repository)
    issue = models.ForeignKey(Issue)
    created_at = models.DateTimeField(db_index=True)
    title = models.TextField()

    related_content_type = models.ForeignKey(ContentType, blank=True, null=True)
    related_object_id = models.PositiveIntegerField(blank=True, null=True, db_index=True)
    related_object = generic.GenericForeignKey('related_content_type',
                                               'related_object_id')

    RENDERERS = {
        'issue': IssueRenderer,
    }

    def __unicode__(self):
        return u'%s' % self.title

    @property
    def renderer(self):
        if not hasattr(self, '_renderer'):
            self._renderer = self.RENDERERS[self.related_content_type.model](self)
        return self._renderer

    def render_as_text(self):
        pass

    def render_as_html(self):
        pass


class EventPart(models.Model):
    event = models.ForeignKey(Event, related_name='parts')
    field = models.CharField(max_length=50, db_index=True)
    old_value = JSONField()
    new_value = JSONField()

    def __unicode__(self):
        return u'%s: %s' % (self.event, self.field)

    @property
    def renderer(self):
        return self.event.renderer

    def render_as_text(self):
        try:
            return getattr(self.renderer, 'render_%s' % self.field)(self, 'text')
        except Exception:
            return '%s has changed' % self.field.capitalize()

    def render_as_html(self):
        try:
            return getattr(self.renderer, 'render_%s' % self.field)(self, 'html')
        except Exception:
            return '%s has changed' % self.field
