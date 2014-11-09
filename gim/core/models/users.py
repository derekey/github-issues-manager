__all__ = [
    'AVAILABLE_PERMISSIONS',
    'AvailableRepository',
    'GithubUser',
    'Team',
]

from django.contrib.auth.models import AbstractUser
from django.db import models

from extended_choices import Choices

from .. import GITHUB_HOST

from ..ghpool import (
    ApiError,
    ApiNotFoundError,
    Connection,
)
from ..managers import (
    AvailableRepositoryManager,
    GithubObjectManager,
    GithubUserManager,
)

from .base import (
    GithubObject,
    GithubObjectWithId,
)

import username_hack  # force the username length to be 255 chars


AVAILABLE_PERMISSIONS = Choices(
    ('pull', 'pull', 'Simple user'),  # can read, create issues
    ('push', 'push', 'Collaborator'),  # can push, manage issues
    ('admin', 'admin', 'Admin'),  # can admin, push, manage issues
)


class GithubUser(GithubObjectWithId, AbstractUser):
    # username will hold the github "login"
    token = models.TextField(blank=True, null=True)
    avatar_url = models.TextField(blank=True, null=True)
    is_organization = models.BooleanField(default=False)
    organizations = models.ManyToManyField('self', related_name='members')
    organizations_fetched_at = models.DateTimeField(blank=True, null=True)
    organizations_etag = models.CharField(max_length=64, blank=True, null=True)
    teams = models.ManyToManyField('Team', related_name='members')
    teams_fetched_at = models.DateTimeField(blank=True, null=True)
    teams_etag = models.CharField(max_length=64, blank=True, null=True)
    available_repositories = models.ManyToManyField('Repository', through='AvailableRepository')
    watched_repositories = models.ManyToManyField('Repository', related_name='watched')
    starred_repositories = models.ManyToManyField('Repository', related_name='starred')

    objects = GithubUserManager()

    github_matching = dict(GithubObjectWithId.github_matching)
    github_matching.update({
        'login': 'username',
    })
    github_ignore = GithubObjectWithId.github_ignore + ('token', 'is_organization', 'password',
        'is_staff', 'is_active', 'date_joined', 'username', ) + ('following_url', 'events_url',
        'organizations_url', 'url', 'gists_url', 'html_url', 'subscriptions_url', 'repos_url',
        'received_events_url', 'gravatar_id', 'starred_url', 'site_admin', 'type', 'followers_url', )

    class Meta:
        app_label = 'core'
        ordering = ('username', )

    @property
    def github_url(self):
        return GITHUB_HOST + self.username

    @property
    def github_organization_url(self):
        return GITHUB_HOST + 'orgs/' + self.username

    @property
    def github_callable_identifiers(self):
        return [
            'users',
            self.username,
        ]

    @property
    def github_callable_identifiers_for_self(self):
        # api.github.com/user
        return [
            'user',
        ]

    @property
    def github_callable_identifiers_for_organization(self):
        return [
            'orgs',
            self.username,
        ]

    @property
    def github_callable_identifiers_for_organizations(self):
        return self.github_callable_identifiers + [
            'orgs',
        ]

    @property
    def github_callable_identifiers_for_teams(self):
        if self.is_organization:
            return self.github_callable_identifiers_for_organization + [
                'teams',
            ]
        else:
            return self.github_callable_identifiers_for_self + [
                'teams',
            ]

    @property
    def github_callable_identifiers_for_available_repositories_set(self):
        # won't work for organizations, but not called in this case
        return self.github_callable_identifiers_for_self + [
            'repos',
        ]

    @property
    def github_callable_identifiers_for_starred_repositories(self):
        # won't work for organizations, but not called in this case
        return self.github_callable_identifiers_for_self + [
            'starred',
        ]

    @property
    def github_callable_identifiers_for_watched_repositories(self):
        # won't work for organizations, but not called in this case
        return self.github_callable_identifiers_for_self + [
            'subscriptions',
        ]

    def __getattr__(self, name):
        """
        We create "github_identifiers_for" to fetch repositories of an
        organization by calling it from the user, so we must create it on the
        fly.
        """
        if name.startswith('github_callable_identifiers_for_org_repositories_'):
            org_name = name[49:]
            return [
                'orgs',
                org_name,
                'repos'
            ]

        raise AttributeError("%r object has no attribute %r" % (self.__class__, name))

    def fetch_organizations(self, gh, force_fetch=False, parameters=None):
        if self.is_organization:
            # an organization cannot belong to an other organization
            return 0

        # force fetching 100 orgs by default, as we cannot set "github_per_page"
        # for the whole GithubUser class
        if not parameters:
            parameters = {}
        if 'per_page' not in parameters:
            parameters['per_page'] = 100

        return self._fetch_many('organizations', gh,
                                defaults={'simple': {'is_organization': True}},
                                force_fetch=force_fetch,
                                parameters=parameters)

    def fetch_teams(self, gh, force_fetch=False, parameters=None):
        defaults = None
        if self.is_organization:
            defaults = {'fk': {'organization': self}}
        return self._fetch_many('teams', gh,
                                defaults=defaults,
                                force_fetch=force_fetch,
                                parameters=parameters)

    def fetch_starred_repositories(self, gh=None, force_fetch=False, parameters=None):
        # FORCE GH
        if not gh or gh._connection_args.get('username') != self.username:
            gh = self.get_connection()

        # force fetching 100 orgs by default, as we cannot set "github_per_page"
        # for the whole Repository class
        if not parameters:
            parameters = {}
        if 'per_page' not in parameters:
            parameters['per_page'] = 100

        return self._fetch_many('starred_repositories', gh,
                                force_fetch=force_fetch,
                                parameters=parameters)

    def fetch_watched_repositories(self, gh=None, force_fetch=False, parameters=None):
        # FORCE GH
        if not gh or gh._connection_args.get('username') != self.username:
            gh = self.get_connection()

        # force fetching 100 orgs by default, as we cannot set "github_per_page"
        # for the whole Repository class
        if not parameters:
            parameters = {}
        if 'per_page' not in parameters:
            parameters['per_page'] = 100

        return self._fetch_many('watched_repositories', gh,
                                force_fetch=force_fetch,
                                parameters=parameters)

    def fetch_available_repositories(self, gh=None, force_fetch=False, org=None, parameters=None):
        """
        Fetch available repositories for the current user (the "gh" will be
        forced").
        It will fetch the repositories available within an organization if "org"
        is filled, and if not, it will fecth the other repositories available to
        the user: ones he owns, or ones where he is a collaborator.
        """
        if self.is_organization:
            # no available repositories for an organization as they can't login
            return 0

        # force fetching 100 orgs by default, as we cannot set "github_per_page"
        # for the whole Repository class
        if not parameters:
            parameters = {}
        if 'per_page' not in parameters:
            parameters['per_page'] = 100

        # FORCE GH
        if not gh or gh._connection_args.get('username') != self.username:
            gh = self.get_connection()

        # force to work on current user
        if gh._connection_args['username'] == self.username:
            user = self
        else:
            user = GithubUser.objects.get(username=gh._connection_args['username'])

        defaults = {'fk': {'user': user}}

        if org:
            filter_queryset = models.Q(organization_id=org.id)
            meta_base_name = 'org_repositories_' + org.username
            defaults['simple'] = {
                'organization_id': org.id,
                'organization_username': org.username,
            }
        else:
            filter_queryset = models.Q(organization_id__isnull=True)
            meta_base_name = None
            defaults['simple'] = {
                'organization_id': None,
                'organization_username': None,
            }

        try:
            return self._fetch_many('available_repositories_set', gh,
                                    meta_base_name=meta_base_name,
                                    defaults=defaults,
                                    force_fetch=force_fetch,
                                    parameters=parameters,
                                    filter_queryset=filter_queryset)
        except ApiNotFoundError:
            # no access to this list, remove all repos
            self.available_repositories_set.filter(filter_queryset).delete()
            return 0

    def fetch_all(self, gh=None, force_fetch=False, **kwargs):
        # FORCE GH
        if not gh or gh._connection_args.get('username') != self.username:
            gh = self.get_connection()

        super(GithubUser, self).fetch_all(gh, force_fetch=force_fetch)

        if self.is_organization:
            return 0, 0, 0, 0, 0

        if not self.token:
            return 0, 0, 0, 0, 0

        # repositories a user own or collaborate to, but not in organizations
        nb_repositories_fetched = self.fetch_available_repositories(gh, force_fetch=force_fetch)

        # repositories in the user's organizations
        nb_orgs_fetched = self.fetch_organizations(gh, force_fetch=force_fetch)
        for org in self.organizations.all():
            nb_repositories_fetched += self.fetch_available_repositories(gh, org=org, force_fetch=force_fetch)

        # check old organizations (the user has avail repos in this org, but it's not an org he is part of)
        old_orgs = GithubUser.objects.filter(
            is_organization=True,
            owned_repositories__availablerepository__user=self
        ).exclude(id__in=self.organizations.all()).distinct()

        for org in old_orgs:
            nb_repositories_fetched += self.fetch_available_repositories(gh, org=org, force_fetch=True)

        # manage starred and watched
        if not kwargs.get('available_only'):
            nb_watched = self.fetch_watched_repositories(gh, force_fetch=force_fetch)
            nb_starred = self.fetch_starred_repositories(gh, force_fetch=force_fetch)
        else:
            nb_watched = 0
            nb_starred = 0

        # # repositories on organizations teams the user are a collaborator
        # try:
        #     nb_teams_fetched = self.fetch_teams(gh, force_fetch=force_fetch)
        # except ApiNotFoundError:
        #     # we may have no rights
        #     pass
        # else:
        #     for team in self.teams.all():
        #         try:
        #             team.fetch_repositories(gh, force_fetch=force_fetch)
        #         except ApiNotFoundError:
        #             # we may have no rights
        #             pass

        # update permissions in token object
        t = self.token_object
        if t:
            t.update_repos()

        return nb_repositories_fetched, nb_orgs_fetched, nb_watched, nb_starred, 0  # nb_teams_fetched

    def get_connection(self):
        return Connection.get(username=self.username, access_token=self.token)

    @property
    def token_object(self):
        """
        Return the "Token" object for the current user, creating it if needed
        """
        if not hasattr(self, '_token_object'):
            if not self.token:
                return None
            from ..limpyd_models import Token
            self._token_object, created = Token.get_or_connect(token=self.token)
            if created:
                self._token_object.username.hset(self.username)
        return self._token_object

    def can_use_repository(self, repository):
        """
        Return 'admin', 'push' or 'read' if the user can use this repository
        ('admin' if he has admin rights, 'push' if push rights, else 'read')
        The repository can be a real repository object, a tuple with two entries
        (the owner's username and the repository name), or a string on the
        github format: "username/reponame"
        The user can use this repository if it has admin/push/read rights.
        It's done by fetching the repository via the github api, and if the
        users can push/admin it, the repository is updated (if it's a real
        repository object).
        The result will be None if a problem occured during the check.
        """
        from .repositories import Repository

        gh = self.get_connection()

        is_real_repository = isinstance(repository, Repository)

        if is_real_repository:
            identifiers = repository.github_callable_identifiers
        else:
            if isinstance(repository, basestring):
                parts = repository.split('/')
            else:
                parts = list(repository)
            identifiers = ['repos'] + parts

        gh_callable = Repository.objects.get_github_callable(gh, identifiers)
        try:
            repo_infos = gh_callable.get()
        except ApiNotFoundError:
            return False
        except ApiError, e:
            if e.response and e.response.code and e.response.code in (401, 403):
                return False
            return None
        except:
            return None

        if not repo_infos:
            return False

        permissions = repo_infos.get('permissions', {'admin': False, 'pull': True, 'push': False})

        if permissions.get('pull', False):
            can_admin = permissions.get('admin', False)
            can_push = permissions.get('push', False)

            if is_real_repository and (can_admin or can_push):
                Repository.objects.create_or_update_from_dict(repo_infos)

            return 'admin' if can_admin else 'push' if can_push else 'read'

        return False

    def save(self, *args, **kwargs):
        """
        Save the user but override to set the mail not set to '' (None not
        allowed from AbstractUser)
        """
        if self.email is None:
            self.email = ''
        super(GithubUser, self).save(*args, **kwargs)


class Team(GithubObjectWithId):
    organization = models.ForeignKey('GithubUser', related_name='org_teams')
    name = models.TextField()
    slug = models.TextField()
    permission = models.CharField(max_length=5)
    repositories = models.ManyToManyField('Repository', related_name='teams')
    repositories_fetched_at = models.DateTimeField(blank=True, null=True)
    repositories_etag = models.CharField(max_length=64, blank=True, null=True)

    objects = GithubObjectManager()

    github_ignore = GithubObjectWithId.github_ignore + ('members_url',
                    'repositories_url', 'url', 'repos_count', 'members_count')

    github_per_page = {'min': 100, 'max': 100}

    class Meta:
        app_label = 'core'
        ordering = ('name', )

    def __unicode__(self):
        return u'%s - %s' % (self.organization.username, self.name)

    @property
    def github_url(self):
        return self.organization.github_organization_url + '/teams/' + self.name

    @property
    def github_callable_identifiers(self):
        return [
            'teams',
            self.github_id,
        ]

    def fetch_all(self, gh, force_fetch=False, **kwargs):
        super(Team, self).fetch_all(gh, force_fetch, **kwargs)
        try:
            self.fetch_repositories(gh, force_fetch=force_fetch)
        except ApiNotFoundError:
            # we may have no rights
            pass

    @property
    def github_callable_identifiers_for_repositories(self):
        return self.github_callable_identifiers + [
            'repos',
        ]

    def fetch_repositories(self, gh, force_fetch=False, parameters=None):

        # force fetching 100 orgs by default, as we cannot set "github_per_page"
        # for the whole Repository class
        if not parameters:
            parameters = {}
        if 'per_page' not in parameters:
            parameters['per_page'] = 100

        return self._fetch_many('repositories', gh,
                                force_fetch=force_fetch,
                                parameters=parameters)


class AvailableRepository(GithubObject):
    """
    Will host repositories a user can access ("through" table for user.available_repositories)
    """
    user = models.ForeignKey('GithubUser', related_name='available_repositories_set')
    repository = models.ForeignKey('Repository')
    permission = models.CharField(max_length=5, choices=AVAILABLE_PERMISSIONS.CHOICES)
    # cannot use another FK to GithubUser as its a through table :(
    organization_id = models.PositiveIntegerField(blank=True, null=True)
    organization_username = models.CharField(max_length=255, blank=True, null=True)

    objects = AvailableRepositoryManager()

    github_identifiers = {
        'repository__github_id': ('repository', 'github_id'),
        'user__username': ('user', 'username'),
    }

    class Meta:
        app_label = 'core'
        unique_together = (
            ('user', 'repository'),
        )
        ordering = ('organization_username', 'repository',)

    def __unicode__(self):
        return '%s can "%s" %s (org: %s)' % (self.user, self.permission, self.repository, self.organization_username)
