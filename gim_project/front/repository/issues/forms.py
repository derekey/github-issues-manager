from datetime import datetime

from django import forms

from core.models import Issue, IssueComment, PullRequestComment

from front.mixins.forms import (LinkedToUserFormMixin, LinkedToIssueFormMixin,
                                LinkedToRepositoryFormMixin)


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
            raise forms.ValidationError('State not updated')
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


def validate_filled_string(value):
    if not value or not value.strip():
        raise forms.ValidationError('You must enter a comment')


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
