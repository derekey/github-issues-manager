from django.core.urlresolvers import reverse_lazy

from core.models import Repository as _Repository

# load all other models to use from front.models and not core.models
from core.models import GithubUser, Milestone, LabelType, Label, Issue, IssueComment


class Repository(_Repository):
    class Meta:
        proxy = True

    def get_reverse_kwargs(self):
        """
        Return the kwargs to use for "reverse"
        """
        return {
            'owner_username': self.owner.username,
            'repository_name': self.name,
        }

    def get_absolute_url(self):
        return reverse_lazy('front:repository:home', kwargs=self.get_reverse_kwargs())
