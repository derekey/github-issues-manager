
from urlparse import urlsplit, parse_qs
from itertools import product

from django.db import models
from django.contrib.auth.models import AbstractUser

from .ghpool import parse_header_links
from .managers import (GithubObjectManager, WithRepositoryManager,
                       IssueCommentManager, GithubUserManager, IssueManager,
                       RepositoryManager)
import username_hack  # force the username length to be 255 chars


class GithubObject(models.Model):
    fetched_at = models.DateTimeField()

    objects = GithubObjectManager()

    github_matching = {}
    github_ignore = ()
    github_format = '+json'

    class Meta:
        abstract = True

    def _prepare_fetch_headers(self):
        """
        Prepare and return the headers to use for the github call..
        """
        headers = {
            'Accept': 'application/vnd.github%s' % self.github_format
        }
        return headers

    def fetch(self, auth):
        """
        Fetch data from github for the current object and update itself.
        """
        identifiers = self.github_callable_identifiers

        request_headers = self._prepare_fetch_headers()
        response_headers = {}

        obj = self.__class__.objects.get_from_github(auth, identifiers,
                                None, request_headers, response_headers)

        if obj is None:
            return False

        self.__dict__.update(obj.__dict__)

        return True

    def fetch_many(self, field_name, auth, vary=None):
        """
        Fetch data from github for the given m2m or related field.
        """
        field, _, direct, _ = self._meta.get_field_by_name(field_name)
        if direct:
            # we are on a field of the current model, the objects to create or
            # update are on the model on the other side of the relation
            model = field.related.parent_model
        else:
            # the field is originally defined on the other side of the relation,
            # we have a RelatedObject with the model on the other side of the
            # relation to use to create or update are on the current model
            model = field.model

        identifiers = getattr(self, 'github_callable_identifiers_for_%s' % field_name)

        request_headers = self._prepare_fetch_headers()

        objs = []

        def fetch_page_and_next(objs, parameters):
            """
            Fetch a page of objects with the given parameters, and if github
            tell us there is a "next" page, continue fetching

            """
            response_headers = {}

            page_objs = model.objects.get_from_github(auth, identifiers,
                                parameters, request_headers, response_headers)

            objs += page_objs

            # if we have a next page, got fetch it
            if 'link' in response_headers:
                links = parse_header_links(response_headers['link'])
                if 'next' in links and 'url' in links['next']:
                    next_page_parameters = parameters.copy()
                    next_page_parameters.update(
                        dict(
                            (k, v[0]) for k, v in parse_qs(
                                    urlsplit(links['next']['url']).query
                                ).items() if len(v)
                            )
                    )
                    fetch_page_and_next(objs, next_page_parameters)

        if not vary:
            # no varying parameter, fetch with an empty set of parameters
            parameters_dicts = [{}]
        else:
            # create all combinations of varying parameters
            vary_keys = sorted(vary)
            parameters_dicts = [dict(zip(vary_keys, prod)) for prod in product(*(vary[key] for key in vary_keys))]

        # fetch data for each combination of varying parameters
        for parameters in parameters_dicts:
            fetch_page_and_next(objs, parameters)

        # now update the list with created/updated objects
        instance_field = getattr(self, field_name)

        if hasattr(instance_field, 'clear'):
            # if FK, only objects with nullable FK have a clear method, so we
            # only clear if the model allows us to
            instance_field.clear()

        # add new objects (won't touch existing ones)
        instance_field.add(*objs)

        if not objs:
            return 0
        else:
            return len(objs)


class GithubObjectWithId(GithubObject):
    github_id = models.PositiveIntegerField(unique=True)

    github_matching = {
        'id': 'github_id'
    }
    github_identifiers = {'github_id': 'github_id'}

    class Meta:
        abstract = True


class GithubUser(GithubObjectWithId, AbstractUser):
    # username will hold the github "login"
    token = models.TextField()
    avatar_url = models.TextField()
    is_organization = models.BooleanField(default=False)

    objects = GithubUserManager()

    github_matching = dict(GithubObjectWithId.github_matching)
    github_matching.update({
        'login': 'username',
    })
    github_ignore = GithubObjectWithId.github_ignore + ('token',
        'is_organization', 'password', 'is_staff', 'is_active', 'date_joined')

    @property
    def github_callable_identifiers(self):
        return [
            'users',
            self.username,
        ]


class Repository(GithubObjectWithId):
    owner = models.ForeignKey(GithubUser, related_name='owned_repositories')
    name = models.TextField(db_index=True)
    description = models.TextField(blank=True, null=True)
    collaborators = models.ManyToManyField(GithubUser, related_name='repositories')

    objects = RepositoryManager()

    class Meta:
        unique_together = (
            ('owner', 'name'),
        )

    @property
    def github_callable_identifiers(self):
        return [
            'repos',
            self.owner.username,
            self.name,
        ]

    @property
    def github_callable_identifiers_for_collaborators(self):
        return self.github_callable_identifiers + [
            'collaborators',
        ]

    def fetch_collaborators(self, auth):
        return self.fetch_many('collaborators', auth)

    @property
    def github_callable_identifiers_for_labels(self):
        return self.github_callable_identifiers + [
            'labels',
        ]

    def fetch_labels(self, auth):
        return self.fetch_many('labels', auth)

    @property
    def github_callable_identifiers_for_milestones(self):
        return self.github_callable_identifiers + [
            'milestones',
        ]

    def fetch_milestones(self, auth):
        return self.fetch_many('milestones', auth, vary={'state': ('open', 'closed')})

    @property
    def github_callable_identifiers_for_issues(self):
        return self.github_callable_identifiers + [
            'issues',
        ]

    def fetch_issues(self, auth):
        return self.fetch_many('issues', auth, vary={'state': ('open', 'closed')})


class LabelType(models.Model):
    repository = models.ForeignKey(Repository, related_name='label_types')
    regex = models.TextField()
    name = models.TextField(db_index=True)

    class Meta:
        unique_together = (
            ('repository', 'name'),
        )

    def match(self, name):
        pass

    def get_typed_name(self, name):
        pass


class Label(GithubObject):
    repository = models.ForeignKey(Repository, related_name='labels')
    name = models.TextField()
    color = models.CharField(max_length=6)
    label_type = models.ForeignKey(LabelType, related_name='labels', blank=True, null=True)
    typed_name = models.TextField(db_index=True)

    objects = WithRepositoryManager()

    github_ignore = GithubObject.github_ignore + ('label_type', 'typed_name', )
    github_identifiers = {'repository__github_id': ('repository', 'github_id'), 'name': 'name'}

    class Meta:
        unique_together = (
            ('repository', 'name'),
        )
        ordering = ('name', )

    @property
    def github_callable_identifiers(self):
        return self.repository.github_callable_identifiers_for_labels + [
            self.name,
        ]

    def save(self, *args, **kwargs):
        for label_type in self.repository.label_types.all():
            if label_type.match(self.name):
                self.label_type = label_type
                self.typed_name = label_type.get_typed_name(self.name)
                break
        if not self.label_type:
            self.typed_name = self.name

        super(Label, self).save(*args, **kwargs)


class Milestone(GithubObjectWithId):
    repository = models.ForeignKey(Repository, related_name='milestones')
    number = models.PositiveIntegerField(db_index=True)
    title = models.TextField(db_index=True)
    description = models.TextField(blank=True, null=True)
    state = models.CharField(max_length=10, db_index=True)
    created_at = models.DateTimeField(db_index=True)
    due_on = models.DateTimeField(db_index=True, blank=True, null=True)
    creator = models.ForeignKey(GithubUser, related_name='milestones')

    objects = WithRepositoryManager()

    class Meta:
        unique_together = (
            ('repository', 'number'),
        )
        ordering = ('number', )

    @property
    def github_callable_identifiers(self):
        return self.repository.github_callable_identifiers_for_milestones + [
            self.number,
        ]


class Issue(GithubObjectWithId):
    repository = models.ForeignKey(Repository, related_name='issues')
    number = models.PositiveIntegerField(db_index=True)
    title = models.TextField(db_index=True)
    body = models.TextField(blank=True, null=True)
    labels = models.ManyToManyField(Label, related_name='issues')
    user = models.ForeignKey(GithubUser, related_name='created_issues')
    assignee = models.ForeignKey(GithubUser, related_name='assigned_issues', blank=True, null=True)
    created_at = models.DateTimeField(db_index=True)
    updated_at = models.DateTimeField(db_index=True)
    closed_at = models.DateTimeField(blank=True, null=True)
    is_pull_request = models.BooleanField(default=False, db_index=True)
    milestone = models.ForeignKey(Milestone, related_name='issues', blank=True, null=True)
    state = models.CharField(max_length=10, db_index=True)

    objects = IssueManager()

    github_matching = dict(GithubObjectWithId.github_matching)
    github_matching.update({
        'body_html': 'body',
    })
    github_ignore = GithubObject.github_ignore + ('is_pull_request', 'comments', )
    github_format = '.html+json'

    class Meta:
        unique_together = (
            ('repository', 'number'),
        )

    @property
    def github_callable_identifiers(self):
        return self.repository.github_callable_identifiers_for_issues + [
            self.number,
        ]

    @property
    def github_callable_identifiers_for_comments(self):
        return self.github_callable_identifiers + [
            'comments',
        ]

    def fetch_comments(self, auth):
        return self.fetch_many('comments', auth)

    @property
    def github_callable_identifiers_for_labels(self):
        return self.github_callable_identifiers + [
            'labels',
        ]

    def fetch_labels(self, auth):
        return self.fetch_many('labels', auth)

    @property
    def github_callable_identifiers_for_label(self, label):
        return self.github_callable_identifiers_for_labels + [
            label.name,
        ]


class IssueComment(GithubObjectWithId):
    issue = models.ForeignKey(Issue, related_name='comments')
    user = models.ForeignKey(GithubUser, related_name='issue_comments')
    body = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(db_index=True)
    updated_at = models.DateTimeField(db_index=True)

    objects = IssueCommentManager()

    github_matching = dict(GithubObjectWithId.github_matching)
    github_matching.update({
        'body_html': 'body',
    })
    github_format = '.html+json'

    class Meta:
        ordering = ('created_at', )

    @property
    def github_callable_identifiers(self):
        return self.repository.github_callable_identifiers_for_issues + [
            'comments',
            self.github_id,
        ]
