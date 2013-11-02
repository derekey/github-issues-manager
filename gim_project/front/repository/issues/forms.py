from django.forms import models

from core.models import Issue

from front.repository.forms import LinkedToRepositoryForm


class IssueFormMixin(LinkedToRepositoryForm):
    class Meta:
        model = Issue


class IssueStateForm(IssueFormMixin):
    class Meta(IssueFormMixin.Meta):
        fields = []

    def __init__(self, *args, **kwargs):
        self.state = kwargs.pop('state')
        super(IssueStateForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        self.instance.state = self.state
        return super(IssueStateForm, self).save(commit)
