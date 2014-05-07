from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.db import models

from jsonfield import JSONField

from core.models import Repository, Issue
from core.utils import contribute_to_model

from .renderers import IssueRenderer

import django_m2m_descriptor_hack  # replace clear+add by remove+add


class Event(models.Model):
    repository = models.ForeignKey(Repository)
    issue = models.ForeignKey(Issue)
    created_at = models.DateTimeField(db_index=True)
    title = models.TextField()
    is_update = models.BooleanField()

    related_content_type = models.ForeignKey(ContentType, blank=True, null=True)
    related_object_id = models.PositiveIntegerField(blank=True, null=True, db_index=True)
    related_object = generic.GenericForeignKey('related_content_type',
                                               'related_object_id')

    RENDERERS = {
        'issue': IssueRenderer,
    }

    renderer_ignore_fields = []

    class Meta:
        ordering = ('created_at', )

    def __unicode__(self):
        return u'%s' % self.title

    @property
    def renderer(self):
        if not hasattr(self, '_renderer'):
            self._renderer = self.RENDERERS[self.related_content_type.model](self)
        return self._renderer

    def get_parts(self, ignore_fields=None):
        parts = list(self.parts.all())
        if ignore_fields is None:
            ignore_fields = self.renderer_ignore_fields
        if ignore_fields:
            ignore_fields = set(ignore_fields)
            parts = [p for p in parts if p.field not in ignore_fields]
        return parts

    def get_part(self, field):
        try:
            return [p for p in self.parts.all() if p.field == field][0]
        except IndexError:
            return None

    def render_as_text(self, ignore_fields=None):
        try:
            return self.renderer.render_as_text()
        except AttributeError:
            parts = list(self.get_parts(ignore_fields))
            params = {
                'title': self.renderer.render_event_title('text'),
            }
            if len(parts):
                result = "%(title)s:\n%(parts)s"
                parts_as_text = [p.render_as_text() for p in parts]
                params['parts'] = '\n'.join('  - %s' % txt for txt in parts_as_text if txt)

            if not params.get('parts'):
                result = "%(title)s"

            return result % params

    def render_as_html(self, ignore_fields=None):
        try:
            return self.renderer.render_as_html()
        except AttributeError:
            parts = list(self.get_parts(ignore_fields))
            params = {
                'title': self.renderer.render_event_title('html'),
            }
            if len(parts):
                result = "<div><strong>%(title)s</strong>:\n<ul class='unstyled'>%(parts)s</ul></div>"
                parts_as_html = [p.render_as_html() for p in parts]
                params['parts'] = '\n'.join('  <li>%s</li>' % html for html in parts_as_html if html)

            if not params.get('parts'):
                result = "<div><strong>%(title)s</strong></div>"

            return result % params

    def add_parts(self, parts):
        # do not use bulk_create as it does not trigger signals
        for part in parts:
            EventPart.objects.create(event=self, **part)


class EventPart(models.Model):
    event = models.ForeignKey(Event, related_name='parts')
    field = models.CharField(max_length=50, db_index=True)
    old_value = JSONField(blank=True, null=True)
    new_value = JSONField(blank=True, null=True)

    class Meta:
        ordering = ('id', )

    def __unicode__(self):
        return u'%s: %s' % (self.event, self.field)

    @property
    def renderer(self):
        return self.event.renderer

    def render_as_text(self):
        try:
            return getattr(self.renderer, 'render_part_%s' % self.field)(self, 'text')
        except Exception:
            return '%s has changed' % self.field.capitalize()

    def render_as_html(self):
        try:
            html_part = getattr(self.renderer, 'render_part_%s' % self.field)(self, 'html')
        except Exception:
            html_part = '%s has changed' % self.field
        if html_part is None:
            return ''
        return '<div class="part-%s">%s</div>' % (self.field, html_part)


from .trackers import *


class _Repository(models.Model):
    class Meta:
        abstract = True

    @property
    def counters(self):
        if not hasattr(self, '_counters_limpyd_object'):
            from .limpyd_models import RepositoryCounters
            self._counters_limpyd_object, created = RepositoryCounters.get_or_connect(repository_id=self.id)
            if created:
                self._counters_limpyd_object.update_global()
                self._counters_limpyd_object.update_users()
        return self._counters_limpyd_object

    def ask_for_counters_update(self):
        from .tasks import ResetRepositoryCounters
        ResetRepositoryCounters.add_job(self.pk, priority=-5, delayed_for=timedelta(minutes=15))

contribute_to_model(_Repository, Repository)


from .tasks import *
