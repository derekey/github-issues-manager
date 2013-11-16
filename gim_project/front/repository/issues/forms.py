from datetime import datetime

from markdown import markdown

from django import forms

from core.models import Issue, IssueComment, PullRequestComment

from front.repository.forms import LinkedToRepositoryForm


class LinkedToUserForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super(LinkedToUserForm, self).__init__(*args, **kwargs)
        if not self.instance.user_id:
            self.instance.user = self.user


class IssueFormMixin(LinkedToRepositoryForm):
    class Meta:
        model = Issue


class IssueStateForm(LinkedToUserForm, IssueFormMixin):
    class Meta(IssueFormMixin.Meta):
        fields = []

    def __init__(self, *args, **kwargs):
        self.state = kwargs.pop('state')
        super(IssueStateForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        self.instance.state = self.state
        if self.state == 'closed':
            self.instance.closed_by = self.user
            self.instance.closed_at = datetime.utcnow()
        else:
            self.instance.closed_by = None
            self.instance.closed_at = None
        return super(IssueStateForm, self).save(commit)


class LinkedToIssueForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        self.issue = kwargs.pop('issue')
        super(LinkedToIssueForm, self).__init__(*args, **kwargs)
        if not self.instance.issue_id:
            self.instance.issue = self.issue
        if not self.instance.repository_id:
            self.instance.repository = self.issue.repository

    def validate_unique(self):
        """
        Calls the instance's validate_unique() method and updates the form's
        validation errors if any were raised.
        """
        exclude = self._get_validation_exclusions()
        if exclude:
            if 'repository' in exclude:
                exclude.remove('repository')
            if 'issue' in exclude:
                exclude.remove('issue')
        try:
            self.instance.validate_unique(exclude=exclude)
        except forms.ValidationError as e:
            self._update_errors(e.message_dict)


def validate_filled_string(value):
    if not value or not value.strip():
        raise forms.ValidationError('You must enter a comment')


class BaseCommentCreateForm(LinkedToUserForm, LinkedToIssueForm):
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
