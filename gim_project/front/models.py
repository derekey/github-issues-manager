from django.core.urlresolvers import reverse, reverse_lazy
from django.db import models

from core import models as core_models
from core.utils import contribute_to_model

from subscriptions import models as subscriptions_models


class _GithubUser(models.Model):
    class Meta:
        abstract = True

    @property
    def hash_for_issue_cache(self):
        """
        Hash for this object representing its state at the current time, used to
        know if we have to reset an issue's cache
        """
        return hash((self.username, self.avatar_url, ))

contribute_to_model(_GithubUser, core_models.GithubUser)


class _Repository(models.Model):
    class Meta:
        abstract = True

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

    def get_view_url(self, url_name):
        return reverse_lazy('front:repository:%s' % url_name,
                                  kwargs=self.get_reverse_kwargs())

    def get_issues_filter_url(self):
        kwargs = self.get_reverse_kwargs()
        return reverse('front:repository:issues', kwargs=kwargs)

    def get_issues_user_filter_url_for_username(self, filter_type, username):
        """
        Return the url to filter issues of this repositories by filter_type, for
        the given username
        Calls are cached for faster access
        """
        cache_key = (self.id, filter_type, username)
        if cache_key not in self.get_issues_user_filter_url_for_username._cache:
            kwargs = self.get_reverse_kwargs()
            kwargs.update({
                'username': username,
                'user_filter_type': filter_type
            })
            self.get_issues_user_filter_url_for_username._cache[cache_key] = \
                        reverse('front:repository:user_issues', kwargs=kwargs)
        return self.get_issues_user_filter_url_for_username._cache[cache_key]
    get_issues_user_filter_url_for_username._cache = {}

contribute_to_model(_Repository, core_models.Repository)


class _LabelType(models.Model):
    class Meta:
        abstract = True

    def get_reverse_kwargs(self):
        """
        Return the kwargs to use for "reverse"
        """
        return {
            'owner_username': self.repository.owner.username,
            'repository_name': self.repository.name,
            'label_type_id': self.id
        }

    def get_edit_url(self):
        from front.repository.dashboard.views import LabelTypeEdit
        return reverse_lazy('front:repository:%s' % LabelTypeEdit.url_name, kwargs=self.get_reverse_kwargs())

    def get_delete_url(self):
        from front.repository.dashboard.views import LabelTypeDelete
        return reverse_lazy('front:repository:%s' % LabelTypeDelete.url_name, kwargs=self.get_reverse_kwargs())

    @property
    def hash_for_issue_cache(self):
        """
        Hash for this object representing its state at the current time, used to
        know if we have to reset an issue's cache
        """
        return hash((self.id, self.name, ))

contribute_to_model(_LabelType, core_models.LabelType)


class _Label(models.Model):
    class Meta:
        abstract = True

    @property
    def hash_for_issue_cache(self):
        """
        Hash for this object representing its state at the current time, used to
        know if we have to reset an issue's cache
        """
        return hash((self.id, self.name, self.color,
                     self.label_type.hash_for_issue_cache
                        if self.label_type_id else None, ))

contribute_to_model(_Label, core_models.Label)


class _Milestone(models.Model):
    class Meta:
        abstract = True

    @property
    def hash_for_issue_cache(self):
        """
        Hash for this object representing its state at the current time, used to
        know if we have to reset an issue's cache
        """
        return hash((self.id, self.name, self.state, ))

contribute_to_model(_Milestone, core_models.Milestone)


class _Issue(models.Model):
    class Meta:
        abstract = True

    def get_reverse_kwargs(self):
        """
        Return the kwargs to use for "reverse"
        """
        return {
            'owner_username': self.repository.owner.username,
            'repository_name': self.repository.name,
            'issue_number': self.number
        }

    def get_absolute_url(self):
        return reverse_lazy('front:repository:issue', kwargs=self.get_reverse_kwargs())

    @property
    def hash_for_cache(self):
        """
        Hash for this issue representing its state at the current time, used to
        know if we have to reset an its cache
        """
        return hash((self.updated_at,
                     self.user.hash_for_issue_cache if self.user_id else None,
                     self.closed_by.hash_for_issue_cache if self.closed_by_id else None,
                     self.assignee.hash_for_issue_cache if self.assignee_id else None,
                     self.milestone.hash_for_issue_cache if self.milestone_id else None,
                     ','.join(
                        ['%d' % l.hash_for_issue_cache for l in self.labels.all()]
                    ),
                ))


contribute_to_model(_Issue, core_models.Issue)


class _WaitingSubscription(models.Model):
    class Meta:
        abstract = True

    def can_add_again(self):
        """
        Return True if the user can add the reposiory again (it is allowed if
        the state is FAILED)
        """
        return self.state == subscriptions_models.WAITING_SUBSCRIPTION_STATES.FAILED

contribute_to_model(_WaitingSubscription, subscriptions_models.WaitingSubscription)
