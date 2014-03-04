from datetime import datetime
from functools import partial

import json

from django import forms
from django.conf import settings
from django.template.defaultfilters import date as convert_date
from django.utils.html import escape

from core.models import Issue, IssueComment, PullRequestComment

from front.mixins.forms import (LinkedToUserFormMixin, LinkedToIssueFormMixin,
                                LinkedToRepositoryFormMixin)


def validate_filled_string(value, name='comment'):
    if not value or not value.strip():
        raise forms.ValidationError('You must enter a %s' % name)


class IssueFormMixin(LinkedToRepositoryFormMixin):
    class Meta:
        model = Issue


class IssueStateForm(LinkedToUserFormMixin, IssueFormMixin):
    user_attribute = None  # don't update issue's user

    class Meta(IssueFormMixin.Meta):
        fields = ['state']

    def clean_state(self):
        new_state = self.cleaned_data.get('state')
        if new_state not in ('open', 'closed'):
            raise forms.ValidationError('Invalide state')
        if new_state == self.instance.state:
            raise forms.ValidationError('The %s was already %s, please reload.' %
                (self.instance.type, 'reopened' if new_state == 'open' else 'closed'))
        return new_state

    def save(self, commit=True):
        self.instance.state = self.cleaned_data['state']
        if self.instance.state == 'closed':
            self.instance.closed_by = self.user
            self.instance.closed_at = datetime.utcnow()
        else:
            self.instance.closed_by = None
            self.instance.closed_at = None
        return super(IssueStateForm, self).save(commit)


class IssueTitleForm(IssueFormMixin):
    class Meta(IssueFormMixin.Meta):
        fields = ['title']

    def __init__(self, *args, **kwargs):
        super(IssueTitleForm, self).__init__(*args, **kwargs)
        self.fields['title'].validators = [partial(validate_filled_string, name='title')]
        self.fields['title'].widget = forms.TextInput()


class IssueBodyForm(IssueFormMixin):
    class Meta(IssueFormMixin.Meta):
        fields = ['body']

    def save(self, commit=True):
        self.instance.body_html = None  # will be reset with data from github
        return super(IssueBodyForm, self).save(commit)


class IssueMilestoneForm(IssueFormMixin):
    class Meta(IssueFormMixin.Meta):
        fields = ['milestone']

    def __init__(self, *args, **kwargs):
        super(IssueMilestoneForm, self).__init__(*args, **kwargs)
        milestones = self.repository.milestones.all().order_by('state', '-number')
        self.fields['milestone'].queryset = milestones
        self.fields['milestone'].widget.choices = self.get_milestones_choices(milestones)
        self.fields['milestone'].widget.attrs.update({
            'data-milestones': self.get_milestones_json(milestones),
            'placeholder': 'Choose a milestone',
        })

    def get_milestones_json(self, milestones):
        data = {m.id: {
                        'id': m.id,
                        'number': m.number,
                        'due_on': convert_date(m.due_on, settings.DATE_FORMAT) if m.due_on else None,
                        'title': escape(m.title),
                        'state': m.state,
                      }
                for m in milestones}
        return json.dumps(data)

    def get_milestones_choices(self, milestones):
        data = {}
        for milestone in milestones:
            data.setdefault(milestone.state, []).append(
                (milestone.id, milestone.title)
            )
        return [('', 'No milestone')] + list(data.items())


class BaseCommentCreateForm(LinkedToUserFormMixin, LinkedToIssueFormMixin):
    class Meta:
        fields = ['body', ]

    def __init__(self, *args, **kwargs):
        super(BaseCommentCreateForm, self).__init__(*args, **kwargs)
        self.fields['body'].validators = [validate_filled_string]
        self.fields['body'].required = True

    def save(self, commit=True):
        self.instance.created_at = self.instance.updated_at = datetime.utcnow()
        return super(BaseCommentCreateForm, self).save(commit)


class IssueCommentCreateForm(BaseCommentCreateForm):
    class Meta(BaseCommentCreateForm.Meta):
        model = IssueComment


class PullRequestCommentCreateForm(BaseCommentCreateForm):
    class Meta(BaseCommentCreateForm.Meta):
        model = PullRequestComment

    def __init__(self, *args, **kwargs):
        self.entry_point = kwargs.pop('entry_point')
        super(PullRequestCommentCreateForm, self).__init__(*args, **kwargs)
        if not self.instance.entry_point_id:
            self.instance.entry_point = self.entry_point
