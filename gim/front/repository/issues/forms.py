
from datetime import datetime, timedelta
from functools import partial
from collections import OrderedDict

import json

from django import forms
from django.conf import settings
from django.template.defaultfilters import date as convert_date
from django.utils.html import escape

from gim.core.models import (Issue, GITHUB_STATUS_CHOICES,
                             IssueComment, PullRequestComment, CommitComment)

from gim.front.mixins.forms import (LinkedToUserFormMixin, LinkedToIssueFormMixin,
                                    LinkedToCommitFormMixin, LinkedToRepositoryFormMixin)


def validate_filled_string(value, name='comment'):
    if not value or not value.strip():
        raise forms.ValidationError('You must enter a %s' % name)


class IssueFormMixin(LinkedToRepositoryFormMixin):
    change_updated_at = 'exact'  # 'fuzzy' / None

    class Meta:
        model = Issue

    def __init__(self, *args, **kwargs):
        super(IssueFormMixin, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.help_text = None

    def save(self, commit=True):
        """
        Update the updated_at to create a new event at the correct time.
        The real update time from github will be saved via dist_edit which
        does a forced update.
        """
        if self.change_updated_at is not None:
            now = datetime.utcnow()
            if not self.instance.updated_at:
                self.instance.updated_at = now
            elif self.change_updated_at == 'fuzzy':
                if now > self.instance.updated_at + timedelta(seconds=120):
                    self.instance.updated_at = now
            else:  # 'exact'
                if now > self.instance.updated_at:
                    self.instance.updated_at = now
        return super(IssueFormMixin, self).save(commit)


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


class IssueTitleFormPart(object):
    def __init__(self, *args, **kwargs):
        super(IssueTitleFormPart, self).__init__(*args, **kwargs)
        self.fields['title'].validators = [partial(validate_filled_string, name='title')]
        self.fields['title'].widget = forms.TextInput(attrs={'placeholder': 'Title'})


class IssueBodyFormPart(object):
    def __init__(self, *args, **kwargs):
        super(IssueBodyFormPart, self).__init__(*args, **kwargs)
        self.fields['body'].widget.attrs.update({
            'placeholder': 'Description',
            'cols': None,
            'rows': None,
        })

    def save(self, commit=True):
        self.instance.body_html = None  # will be reset with data from github
        return super(IssueBodyFormPart, self).save(commit)


class IssueMilestoneFormPart(object):

    def __init__(self, *args, **kwargs):
        super(IssueMilestoneFormPart, self).__init__(*args, **kwargs)
        milestones = self.repository.milestones.all().order_by('-state', '-number')
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
        data = OrderedDict()
        for milestone in milestones:
            data.setdefault(milestone.state, []).append(
                (milestone.id, milestone.title)
            )
        return [('', 'No milestone')] + list(data.items())


class IssueAssigneeFormPart(object):
    def __init__(self, *args, **kwargs):
        super(IssueAssigneeFormPart, self).__init__(*args, **kwargs)
        collaborators = self.repository.collaborators.all()
        self.fields['assignee'].queryset = collaborators
        self.fields['assignee'].widget.choices = self.get_collaborators_choices(collaborators)
        self.fields['assignee'].widget.attrs.update({
            'data-collaborators': self.get_collaborators_json(collaborators),
            'placeholder': 'Choose an assignee',
        })

    def get_collaborators_json(self, collaborators):
        data = {u.id: {
                        'id': u.id,
                        'avatar_url': u.avatar_url,
                        'username': u.username,
                      }
                for u in collaborators}
        return json.dumps(data)

        collaborators = sorted(self.repository.collaborators.all(), key=lambda u: u.username.lower())

    def get_collaborators_choices(self, collaborators):
        collaborators = sorted(collaborators, key=lambda u: u.username.lower())
        return [('', 'No one assigned')] + [(u.id, u.username) for u in collaborators]


class IssueLabelsFormPart(object):
    simple_label_name = 'Labels'

    def __init__(self, *args, **kwargs):
        super(IssueLabelsFormPart, self).__init__(*args, **kwargs)
        labels = self.repository.labels.select_related('label_type')
        self.fields['labels'].required = False
        self.fields['labels'].queryset = labels
        self.fields['labels'].widget.choices = self.get_labels_choices(labels)
        self.fields['labels'].widget.attrs.update({
            'data-labels': self.get_labels_json(labels),
            'placeholder': 'Choose some labels',
        })

    def get_labels_json(self, labels):
        data = {l.id: {
                        'id': l.id,
                        'name': l.name,
                        'color': l.color,
                        'type': l.label_type.name if l.label_type_id else None,
                        'typed_name': l.typed_name,
                        'search': '%s: %s' % (l.label_type.name, l.typed_name)
                                            if l.label_type_id else l.name,
                      }
                for l in labels}
        return json.dumps(data)

    def get_labels_choices(self, labels):
        data = OrderedDict()
        for label in labels:
            type_name = label.label_type.name if label.label_type_id else self.simple_label_name
            data.setdefault(type_name, []).append(
                (label.id, label.typed_name)
            )
        # move Others at the end
        if self.simple_label_name in data:
            data[self.simple_label_name] = data.pop(self.simple_label_name)
        return data.items()


class IssueTitleForm(IssueTitleFormPart, IssueFormMixin):
    class Meta(IssueFormMixin.Meta):
        fields = ['title']


class IssueBodyForm(IssueBodyFormPart, IssueFormMixin):
    class Meta(IssueFormMixin.Meta):
        fields = ['body']


class IssueMilestoneForm(IssueMilestoneFormPart, IssueFormMixin):
    change_updated_at = 'fuzzy'

    class Meta(IssueFormMixin.Meta):
        fields = ['milestone']


class IssueAssigneeForm(IssueAssigneeFormPart, IssueFormMixin):
    change_updated_at = 'fuzzy'

    class Meta(IssueFormMixin.Meta):
        fields = ['assignee']


class IssueLabelsForm(IssueLabelsFormPart, IssueFormMixin):
    change_updated_at = 'fuzzy'

    class Meta(IssueFormMixin.Meta):
        fields = ['labels']


class IssueCreateForm(IssueTitleFormPart, IssueBodyFormPart,
                      LinkedToUserFormMixin, IssueFormMixin):

    class Meta(IssueFormMixin.Meta):
        fields = ['title', 'body', ]

    user_attribute = 'user'

    def save(self, commit=True):
        self.instance.state = 'open'
        self.instance.comments_count = 0
        self.instance.is_pull_request = False
        self.instance.created_at = datetime.utcnow()
        return super(IssueCreateForm, self).save(commit)


class IssueCreateFormFull(IssueMilestoneFormPart, IssueAssigneeFormPart,
                          IssueLabelsFormPart, IssueCreateForm):

    class Meta(IssueCreateForm.Meta):
        fields = ['title', 'body', 'milestone', 'assignee', 'labels']


class BaseCommentEditForm(LinkedToUserFormMixin, LinkedToIssueFormMixin):
    class Meta:
        fields = ['body', ]

    def __init__(self, *args, **kwargs):
        super(BaseCommentEditForm, self).__init__(*args, **kwargs)
        self.fields['body'].validators = [validate_filled_string]
        self.fields['body'].required = True

    def save(self, commit=True):
        if self.instance.pk:
            self.instance.github_status = GITHUB_STATUS_CHOICES.WAITING_UPDATE
        else:
            self.instance.github_status = GITHUB_STATUS_CHOICES.WAITING_CREATE
        self.instance.body_html = None
        self.instance.updated_at = datetime.utcnow()
        if not self.instance.created_at:
            self.instance.created_at = self.instance.updated_at
        return super(BaseCommentEditForm, self).save(commit)


class IssueCommentCreateForm(BaseCommentEditForm):
    class Meta(BaseCommentEditForm.Meta):
        model = IssueComment


class IssueCommentEditForm(BaseCommentEditForm):
    user_attribute = None

    class Meta(BaseCommentEditForm.Meta):
        model = IssueComment


class PullRequestCommentCreateForm(BaseCommentEditForm):
    class Meta(BaseCommentEditForm.Meta):
        model = PullRequestComment

    def __init__(self, *args, **kwargs):
        self.entry_point = kwargs.pop('entry_point')
        super(PullRequestCommentCreateForm, self).__init__(*args, **kwargs)
        if not self.instance.entry_point_id:
            self.instance.entry_point = self.entry_point


class PullRequestCommentEditForm(BaseCommentEditForm):
    user_attribute = None

    class Meta(BaseCommentEditForm.Meta):
        model = PullRequestComment


class CommitCommentCreateForm(LinkedToCommitFormMixin, BaseCommentEditForm):
    class Meta(BaseCommentEditForm.Meta):
        model = CommitComment

    def __init__(self, *args, **kwargs):
        self.entry_point = kwargs.pop('entry_point')
        super(CommitCommentCreateForm, self).__init__(*args, **kwargs)
        if not self.instance.entry_point_id:
            self.instance.entry_point = self.entry_point


class CommitCommentEditForm(LinkedToCommitFormMixin, BaseCommentEditForm):
    user_attribute = None

    class Meta(BaseCommentEditForm.Meta):
        model = CommitComment


class BaseCommentDeleteForm(LinkedToUserFormMixin, LinkedToIssueFormMixin):
    user_attribute = None

    class Meta:
        fields = []

    def save(self, commit=True):
        self.instance.github_status = GITHUB_STATUS_CHOICES.WAITING_DELETE
        return super(BaseCommentDeleteForm, self).save(commit)


class IssueCommentDeleteForm(BaseCommentDeleteForm):
    class Meta(BaseCommentDeleteForm.Meta):
        model = IssueComment


class PullRequestCommentDeleteForm(BaseCommentDeleteForm):
    class Meta(BaseCommentDeleteForm.Meta):
        model = PullRequestComment


class CommitCommentDeleteForm(LinkedToCommitFormMixin, BaseCommentDeleteForm):
    class Meta(BaseCommentDeleteForm.Meta):
        model = CommitComment
