
from urlparse import urlsplit, parse_qs
from itertools import product
from datetime import datetime, timedelta
import re
from operator import itemgetter
import json
import zlib
import base64

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core import validators

from jsonfield import JSONField
from extended_choices import Choices

from .ghpool import parse_header_links, ApiError, ApiNotFoundError, Connection
from .managers import (GithubObjectManager, WithRepositoryManager,
                       IssueCommentManager, GithubUserManager, IssueManager,
                       RepositoryManager, LabelTypeManager)
from .utils import prepare_fetch_headers, MinUpdatedDateRaised

import username_hack  # force the username length to be 255 chars


GITHUB_STATUS_CHOICES = Choices(
    ('WAITING_CREATE', 1, u'Awaiting creation'),
    ('WAITING_UPDATE', 2, u'Awaiting update'),
    ('WAITING_DELETE', 3, u'Awaiting delete'),
    ('FETCHED', 10, u'Fetched'),
    ('ERROR_CREATE', 21, u'Error while creating'),
    ('ERROR_UPDATE', 22, u'Error while updating'),
    ('ERROR_DELETE', 23, u'Error while deleting'),
    ('ERROR_FETCHED', 30, u'Error while fetching'),
)
GITHUB_STATUS_CHOICES.ALL_WAITING = (GITHUB_STATUS_CHOICES.WAITING_CREATE,
                                     GITHUB_STATUS_CHOICES.WAITING_UPDATE,
                                     GITHUB_STATUS_CHOICES.WAITING_DELETE)
GITHUB_STATUS_CHOICES.ALL_ERRORS = (GITHUB_STATUS_CHOICES.ERROR_CREATE,
                                    GITHUB_STATUS_CHOICES.ERROR_UPDATE,
                                    GITHUB_STATUS_CHOICES.ERROR_DELETE,
                                    GITHUB_STATUS_CHOICES.ERROR_FETCHED)


class GithubObject(models.Model):
    fetched_at = models.DateTimeField(null=True, blank=True)
    github_status = models.PositiveSmallIntegerField(
                                choices=GITHUB_STATUS_CHOICES.CHOICES,
                                default=GITHUB_STATUS_CHOICES.WAITING_CREATE,
                                db_index=True)

    objects = GithubObjectManager()

    GITHUB_STATUS_CHOICES = GITHUB_STATUS_CHOICES

    github_matching = {}
    github_ignore = ()
    github_format = '+json'
    github_edit_fields = {'create': (), 'update': ()}

    class Meta:
        abstract = True

    def __str__(self):
        return unicode(self).encode('utf-8')

    def fetch(self, gh, defaults=None, force_fetch=False):
        """
        Fetch data from github for the current object and update itself.
        If defined, "defaults" is a dict with values that will be used if not
        found in fetched data.
        """
        identifiers = self.github_callable_identifiers

        request_headers = prepare_fetch_headers(
                    if_modified_since=None if force_fetch else self.fetched_at,
                    github_format=self.github_format)
        response_headers = {}

        try:
            obj = self.__class__.objects.get_from_github(gh, identifiers,
                            defaults, None, request_headers, response_headers)
        except ApiError, e:
            if e.response and e.response['code'] == 304:
                # github tell us nothing is new, so we stop all the work here
                return True
            else:
                raise

        if obj is None:
            return False

        self.__dict__.update(obj.__dict__)

        return True

    def fetch_all(self, gh, force_fetch=False, **kwargs):
        """
        By default fetch only the current object. Override to add some _fetch_many
        """
        return self.fetch(gh, force_fetch=force_fetch)

    def _fetch_many(self, field_name, gh, vary=None, defaults=None,
                    parameters=None, remove_missing=True, force_fetch=False):
        """
        Fetch data from github for the given m2m or related field.
        If defined, "vary" is a dict of list of parameters to fetch. For each
        key of this dict, all values of the list will be used as a parameter,
        one after the other. If many keys are in "vary", all combinations will
        be fetched.
        If defined, "defaults" is a dict with values that will be used if not
        found in fetched data.
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

        # prepare headers to add in the request
        min_updated_date = None
        if_modified_since = None
        fetched_at_field = '%s_fetched_at' % field_name
        if hasattr(self, fetched_at_field):
            # if we have a fetch date, use it
            fetched_at = getattr(self, fetched_at_field)
            if not force_fetch:
                if fetched_at:
                    # we will stop fetching data when the date of the last
                    # object fetched will be lower than the last updated_at
                    # only if we retrieve objects by last updated first, and
                    # if the model has the updated_at field
                    if (parameters
                            and parameters.get('sort') == 'updated'
                            and parameters.get('direction') == 'desc'
                            and 'updated_at' in model._meta.get_all_field_names()):
                        min_updated_date = fetched_at

                    if_modified_since = fetched_at

        request_headers = prepare_fetch_headers(
                    if_modified_since=if_modified_since,
                    github_format=model.github_format)

        def fetch_page_and_next(objs, parameters, min_updated_date):
            """
            Fetch a page of objects with the given parameters, and if github
            tell us there is a "next" page, tell caller to continue fetching by
            returning the parameters for the next page as first return argument
            (or None if no next page).
            Return the etag header of the page as second argument

            """
            response_headers = {}
            etag = None

            page_objs = []

            try:
                page_objs = model.objects.get_from_github(gh, identifiers,
                        defaults, parameters, request_headers, response_headers)
            except ApiNotFoundError:
                # no data for this list (issues may be no activated, for example)
                pass
            except ApiError, e:
                if e.response and e.response['code'] in (410, ):
                    # no data for this list (issues may be no activated, for example)
                    pass
                else:
                    raise
            except Exception:
                raise

            etag = response_headers.get('etag') or None

            if not page_objs:
                # no fetched objects, we're done
                return None, etag

            objs += page_objs

            # if we reached the min_updated_date, stop
            min_updated_date_raised = False
            if (min_updated_date
                    and page_objs[-1].updated_at < min_updated_date):

                min_updated_date_raised = True

            # if we have a next page, got fetch it
            if 'link' in response_headers:
                links = parse_header_links(response_headers['link'])
                if 'next' in links and 'url' in links['next']:
                    # but only if the min_updated_date wes not raised
                    if not min_updated_date_raised:
                        next_page_parameters = parameters.copy()
                        next_page_parameters.update(
                            dict(
                                (k, v[0]) for k, v in parse_qs(
                                        urlsplit(links['next']['url']).query
                                    ).items() if len(v)
                                )
                        )
                        return next_page_parameters, etag
                else:
                    # we don't have a next_link, we have fetched all page, so
                    # ignore the min_updated_date
                    min_updated_date_raised = False

            if min_updated_date_raised:
                raise MinUpdatedDateRaised(etag)

            return None, etag

        if not vary:
            # no varying parameter, fetch with an empty set of parameters, with
            # a simple etag field
            parameters_combinations = [({}, '%s_etag' % field_name)]
        else:
            # create all combinations of varying parameters
            vary_keys = sorted(vary)
            parameters_combinations_dicts = [
                dict(zip(vary_keys, prod))
                for prod in product(
                    *(vary[key] for key in vary_keys)
                )
            ]

            # get the etag field for each combination
            parameters_combinations = []
            for dikt in parameters_combinations_dicts:
                etag_varation = '_'.join([
                    '%s_%s' % (k, dikt[k])
                    for k in sorted(dikt)
                ])
                etag_field = '%s_%s_etag' % (field_name, etag_varation)
                parameters_combinations.append((dikt, etag_field))

        # add per_page option
        for parameters_combination, _ in parameters_combinations:
            parameters_combination.update({'per_page': 30})
            if parameters:
                parameters_combination.update(parameters)

        # fetch data for each combination of varying parameters
        etags = {}
        objs = []
        cache_hit = False
        something_fetched = False
        for parameters_combination, etag_field in parameters_combinations:

            # use the etag if we have one and we don't have any 200 pages yet
            request_etag = None
            if not force_fetch and hasattr(self, etag_field):
                request_etag = getattr(self, etag_field) or None

                request_headers = prepare_fetch_headers(
                        if_modified_since=if_modified_since,
                        if_none_match=request_etag,
                        github_format=model.github_format)

            try:
                # fetch all available pages
                page = 0
                page_parameters = parameters_combination.copy()
                while True:
                    page += 1
                    page_parameters, page_etag = fetch_page_and_next(objs,
                                            page_parameters, min_updated_date)
                    if page == 1:
                        etags[etag_field] = page_etag
                        if request_etag:
                            # clear if-none-match header for pages > 1
                            request_headers = prepare_fetch_headers(
                                if_modified_since=if_modified_since,
                                if_none_match=None,
                                github_format=model.github_format)

                    if page_parameters is None:
                        break

            except MinUpdatedDateRaised, e:
                etags[etag_field] = e.args[0]
                cache_hit = True

            except ApiError, e:
                if e.response and e.response['code'] == 304:
                    # github tell us nothing is new for this combination
                    cache_hit = True
                    continue
                else:
                    raise

            # at least we fetched something
            something_fetched = True

        # now update the list with created/updated objects
        if something_fetched:
            # but only if we had fresh data !
            self.update_related_field(field_name,
                                      [obj.id for obj in objs],
                                      do_remove=remove_missing and not cache_hit,
                                      etags=etags)

        # we return the number of fetched objects
        if not objs:
            return 0
        else:
            return len(objs)

    def update_related_field(self, field_name, ids, do_remove=True, etags=None):
        """
        For the given field name, with must be a m2m or the reverse side of
        a m2m or a fk, use the given list of ids as the lists of ids of all the
        objects that must be linked.
        Objects that were linked but not in the given list will be removed from
        the relation, or deleted if the relation has a non-nullable link.
        New objects will be simple added to the relation.
        """
        instance_field = getattr(self, field_name)

        count = {'removed': 0, 'added': 0}

        # guess whitch relations to add and whicth to delete
        existing_ids = set(instance_field.values_list('id', flat=True))
        fetched_ids = set(ids or [])

        # if some relations are not here, remove them
        to_remove = existing_ids - fetched_ids
        if do_remove and to_remove:
            count['removed'] = len(to_remove)
            # if FK, only objects with nullable FK have a clear method, so we
            # only clear if the model allows us to
            if hasattr(instance_field, 'remove'):
                # The relation itself can be removed, we remove it but we keep
                # the original object
                # Example: a user is not anymore a collaborator, we keep the
                # the user but remove the relation user <-> repository
                instance_field.remove(*to_remove)
            else:
                # The relation cannot be remove, because the current object is
                # a non-nullable fk of the other objects. In this case we are
                # sure the object is fully deleted on the github side, or
                # attached to another object, but we don't care here, so we
                # delete the objects.
                # Example: a milestone of a repository is not fetched via
                # fetch_milestones, so we know it's deleted
                instance_field.model.objects.filter(id__in=to_remove).delete()

        # if we have new relations, add them
        to_add = fetched_ids - existing_ids
        if to_add:
            count['added'] = len(to_remove)
            instance_field.add(*to_add)

        # check if we have something to save on the main object
        update_fields = []

        # can we save a fetch date ?
        fetched_at_field = '%s_fetched_at' % field_name
        if hasattr(self, fetched_at_field):
            setattr(self, fetched_at_field, datetime.utcnow())
            update_fields.append(fetched_at_field)

        # do we have etags to save ?
        if etags:
            for etag_field, etag in etags.items():
                if hasattr(self, etag_field):
                    setattr(self, etag_field, etag)
                    update_fields.append(etag_field)

        # save main object if needed
        if update_fields:
            self.save(update_fields=update_fields, force_update=True)

        # return count of added and removed data
        return count

    def dist_delete(self, gh):
        """
        Delete the object on the github side, then delete it on our side.
        """
        identifiers = self.github_callable_identifiers
        gh_callable = self.__class__.objects.get_github_callable(gh, identifiers)
        gh_callable.delete()
        self.delete()

    def dist_edit(self, gh, mode, fields=None):
        """
        Edit the object on the github side. Mode can be 'create' or 'update' to
        do the matching action on Github.
        Field sends are defined in github_edit_fields, and the url is defined
        by github_callable_identifiers or github_callable_create_identifiers
        The new/updated object is returned
        """
        # check mode
        if mode not in ('create', 'update'):
            raise Exception('Invalid mode for dist_edit')

        # get fields to send
        if not fields:
            fields = self.github_edit_fields[mode]

        # get data to send
        data = {}

        for field_name in fields:
            if '__' in field_name:
                field_name, subfield_name = field_name.split('__')
                field, _, direct, is_m2m = self._meta.get_field_by_name(field_name)
                relation = getattr(self, field_name)
                if is_m2m or not direct:
                    # we have a many to many relationship
                    data[field_name] = relation.values_list(subfield_name, flat=True)
                else:
                    # we have a foreignkey
                    data[field_name] = None if not relation else getattr(relation, subfield_name)
            else:
                # it's a direct field
                data[field_name] = getattr(self, field_name)
                if isinstance(data[field_name], datetime):
                    data[field_name] = data[field_name].isoformat()

        # prepare the request
        identifiers = self.github_callable_identifiers if mode == 'update' else self.github_callable_create_identifiers
        gh_callable = self.__class__.objects.get_github_callable(gh, identifiers)
        method = getattr(gh_callable, 'patch' if mode == 'update' else 'post')

        # make the request and get fresh data for the object
        result = method(**data)

        # get defaults to update the data with fresh data we just got
        defaults = self.defaults_create_values()

        # if we are in create mode, we delete the object to recreate it with
        # the data we just got
        if mode == 'create':
            self.delete()

        # update the object on our side
        return self.__class__.objects.create_or_update_from_dict(result, defaults)


class GithubObjectWithId(GithubObject):
    github_id = models.PositiveIntegerField(unique=True, null=True, blank=True)

    github_matching = dict(GithubObject.github_matching)
    github_matching.update({
        'id': 'github_id'
    })
    github_identifiers = {'github_id': 'github_id'}

    class Meta:
        abstract = True


class GithubUser(GithubObjectWithId, AbstractUser):
    # username will hold the github "login"
    token = models.TextField(blank=True, null=True)
    avatar_url = models.TextField(blank=True, null=True)
    is_organization = models.BooleanField(default=False)
    organizations = models.ManyToManyField('self', related_name='members')
    organizations_fetched_at = models.DateTimeField(blank=True, null=True)
    organizations_etag = models.CharField(max_length=64, blank=True, null=True)
    _available_repositories = models.TextField(blank=True, null=True)
    available_repositories_fetched_at = models.DateTimeField(blank=True, null=True)

    objects = GithubUserManager()

    github_matching = dict(GithubObjectWithId.github_matching)
    github_matching.update({
        'login': 'username',
    })
    github_ignore = GithubObjectWithId.github_ignore + ('token',
        'is_organization', 'password', 'is_staff', 'is_active', 'date_joined')

    class Meta:
        ordering = ('username', )

    @property
    def github_callable_identifiers(self):
        return [
            'users',
            self.username,
        ]

    @property
    def github_callable_identifiers_for_organizations(self):
        return self.github_callable_identifiers + [
            'orgs',
        ]

    def fetch_organizations(self, gh, force_fetch=False):
        if self.is_organization:
            # an organization cannot belong to an other organization
            return 0
        return self._fetch_many('organizations', gh,
                                defaults={'simple': {'is_organization': True}},
                                force_fetch=force_fetch)

    def fetch_all(self, gh, force_fetch=False, **kwargs):
        super(GithubUser, self).fetch_all(gh, force_fetch=force_fetch)
        self.fetch_organizations(gh, force_fetch=force_fetch)

    def get_connection(self):
        return Connection.get(username=self.username, access_token=self.token)

    def fetch_available_repositories(self):
        """
        Save the list of reositories that the current user can manage in
        Github, and so here. For a repository to be available, it must have
        issues activated, nd the user must at least have "push" access.
        The list is grouped by organizations, with "__self__" the first entry
        listing it's available repositories not in any organization.
        """
        if not self.token:
            return

        gh = self.get_connection()

        def get_repos(identifiers, page, repos_list):
            """
            Function that fetch a page for the given identifiers, adding data to
            the given list, and returning the next page to fetch if any (or None
            if not)
            """
            response_headers = {}
            parameters = {
                'sort': 'pushed',
                'direction': 'desc',
                'page': page,
                'per_page': 100,
            }

            data = Repository.objects.get_data_from_github(
                        gh=gh,
                        identifiers=identifiers,
                        parameters=parameters,
                        response_headers=response_headers)

            # loop on each returned repository
            for datum in data:
                permissions = datum.get('permissions', {'admin': False, 'pull': True, 'push': False})
                can_pull = permissions.get('pull', False)
                can_admin = permissions.get('admin', False)
                can_push = permissions.get('push', False)
                has_issues = datum.get('has_issues', False)

                if can_pull:
                    repos_list.append({
                        'name': datum['name'],
                        'owner': datum['owner']['login'],
                        'private': datum.get('private', False),
                        'pushed_at': datum['pushed_at'],
                        'has_issues': has_issues,
                        'rights': "admin" if can_admin else "push" if can_push else "read",
                        'is_fork': datum.get('fork', False),
                    })

            # check if we have a next page
            if 'link' in response_headers:
                links = parse_header_links(response_headers['link'])
                if 'next' in links and 'url' in links['next']:
                    next_page = parse_qs(urlsplit(links['next']['url']).query).get('page', [])
                    if len(next_page):
                        return next_page[0]

            # no next page !
            return None

        # final lit that will be returned
        all_repos = []
        nb_repos = 0

        self.fetch_organizations(gh)

        # get all lists, one for repos out of any organization ("__self__"), and
        # one for each organization
        repos_lists = [('__self__', ('user', 'repos'))] + [
            (org_name, ('orgs', org_name, 'repos'))
                for org_name in self.organizations.values_list('username', flat=True)
        ]

        for list_name, identifiers in repos_lists:
            repos_list = {'name': list_name,  'repos': []}
            next_page = 1
            while True:
                next_page = get_repos(identifiers, next_page, repos_list['repos'])
                if not next_page:
                    break

            # add the list only if it contains available repositories
            if repos_list['repos']:
                repos_list['repos'].sort(key=itemgetter('pushed_at'), reverse=True)
                all_repos.append(repos_list)
                nb_repos += len(repos_list['repos'])

        # save data and fetch date
        self.available_repositories = all_repos
        self.available_repositories_fetched_at = datetime.utcnow()

        self.save(update_fields=['_available_repositories', 'available_repositories_fetched_at'])

        return (nb_repos, self.organizations.count())

    def _set_available_repositories(self, data):
        """
        Setter for the compressed _available_repositories field
        """
        if not data:
            data = []
        self._available_repositories = base64.encodestring(zlib.compress(json.dumps(data), 9))

    def _get_available_repositories(self):
        """
        Getter for the compressed _available_repositories field
        """
        if not self._available_repositories:
            return []
        return json.loads(zlib.decompress(base64.decodestring(self._available_repositories)))

    available_repositories = property(_get_available_repositories, _set_available_repositories)

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


class Repository(GithubObjectWithId):
    owner = models.ForeignKey(GithubUser, related_name='owned_repositories')
    name = models.TextField(db_index=True)
    description = models.TextField(blank=True, null=True)
    collaborators = models.ManyToManyField(GithubUser, related_name='repositories')
    private = models.BooleanField(default=False)
    is_fork = models.BooleanField(default=False)
    has_issues = models.BooleanField(default=False)

    collaborators_fetched_at = models.DateTimeField(blank=True, null=True)
    collaborators_etag = models.CharField(max_length=64, blank=True, null=True)
    milestones_fetched_at = models.DateTimeField(blank=True, null=True)
    milestones_state_open_etag = models.CharField(max_length=64, blank=True, null=True)
    milestones_state_closed_etag = models.CharField(max_length=64, blank=True, null=True)
    labels_fetched_at = models.DateTimeField(blank=True, null=True)
    labels_etag = models.CharField(max_length=64, blank=True, null=True)
    issues_fetched_at = models.DateTimeField(blank=True, null=True)
    issues_state_open_etag = models.CharField(max_length=64, blank=True, null=True)
    issues_state_closed_etag = models.CharField(max_length=64, blank=True, null=True)
    comments_fetched_at = models.DateTimeField(blank=True, null=True)
    comments_etag = models.CharField(max_length=64, blank=True, null=True)

    objects = RepositoryManager()

    github_matching = dict(GithubObjectWithId.github_matching)
    github_matching.update({
        'fork': 'is_fork',
    })

    class Meta:
        unique_together = (
            ('owner', 'name'),
        )
        ordering = ('owner', 'name', )

    def __unicode__(self):
        return self.full_name

    @property
    def full_name(self):
        return u'%s/%s' % (self.owner.username if self.owner else '?', self.name)

    @property
    def untyped_labels(self):
        """
        Shortcut to return a queryset for untyped labels of the repository
        """
        return self.labels.ready().filter(label_type__isnull=True)

    def _distinct_users(self, relation):
        return GithubUser.objects.filter(**{
                '%s__repository' % relation: self.id
            }).distinct()  # distinct can take the 'username' arg in postgresql

    @property
    def issues_creators(self):
        """
        Shortcut to return a queryset for creator of issues on this repository
        """
        return self._distinct_users('created_issues')

    @property
    def issues_assigned(self):
        """
        Shortcut to return a queryset for users assigned to issues on this repository
        """
        return self._distinct_users('assigned_issues')

    @property
    def issues_closers(self):
        """
        Shortcut to return a queryset for users who closed issues on this repository
        """
        return self._distinct_users('closed_issues')

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

    def fetch_collaborators(self, gh, force_fetch=False):
        return self._fetch_many('collaborators', gh, force_fetch=force_fetch)

    @property
    def github_callable_identifiers_for_labels(self):
        return self.github_callable_identifiers + [
            'labels',
        ]

    def fetch_labels(self, gh, force_fetch=False):
        return self._fetch_many('labels', gh,
                                defaults={'fk': {'repository': self}},
                                force_fetch=force_fetch)

    @property
    def github_callable_identifiers_for_milestones(self):
        return self.github_callable_identifiers + [
            'milestones',
        ]

    def fetch_milestones(self, gh, force_fetch=False):
        return self._fetch_many('milestones', gh,
                                vary={'state': ('open', 'closed')},
                                defaults={'fk': {'repository': self}},
                                force_fetch=force_fetch)

    @property
    def github_callable_identifiers_for_issues(self):
        return self.github_callable_identifiers + [
            'issues',
        ]

    def fetch_issues(self, gh, force_fetch=False, state=None):
        if state:
            vary = {'state': (state, )}
            remove_missing = False
        else:
            vary = {'state': ('open', 'closed')}
            remove_missing = True

        count = self._fetch_many('issues', gh,
                                 vary=vary,
                                 defaults={'fk': {'repository': self}},
                                 parameters={'sort': 'updated', 'direction': 'desc'},
                                 remove_missing=remove_missing,
                                 force_fetch=force_fetch)

        if not state or state == 'closed':
            self.fetch_closed_issues_without_closed_by(gh)

        return count

    def fetch_closed_issues_without_closed_by(self, gh, limit=20):
        # the "closed_by" attribute of an issue is not filled in list call, so
        # we fetch all closed issue that has no closed_by, one by one (but only
        # if we never did it because some times there is noone who closed an
        # issue on the github api :( ))
        issues = list(self.issues.filter(state='closed',
                                        closed_by__isnull=True,
                                        closed_by_fetched=False
                                        ).order_by('-closed_at')[:limit])

        count = 0
        for issue in issues:
            try:
                issue.fetch(gh, force_fetch=True,
                            defaults={'simple': {'closed_by_fetched': True}})
            except ApiError:
                pass
            else:
                count += 1

        if len(issues) == limit:
            from .tasks.repository import FetchClosedIssuesWithNoClosedBy
            FetchClosedIssuesWithNoClosedBy.add_job(self.id,
                                    delayed_for=timedelta(seconds=60),
                                    limit=limit,
                                    gh=gh)

        return count

    @property
    def github_callable_identifiers_for_comments(self):
        return self.github_callable_identifiers_for_issues + [
            'comments',
        ]

    def fetch_comments(self, gh, force_fetch=False):
        return self._fetch_many('comments', gh,
                                defaults={'fk': {'repository': self}},
                                parameters={'sort': 'updated', 'direction': 'desc'},
                                force_fetch=force_fetch)

    def fetch_all(self, gh, force_fetch=False, **kwargs):
        """
        Pass "two_steps=True" to felay fetch of closed issues and comments (by
        adding a FirstFetchStep2 job that will call fetch_all_step2)
        """
        two_steps = bool(kwargs.get('two_steps', False))

        super(Repository, self).fetch_all(gh, force_fetch=force_fetch)
        self.fetch_collaborators(gh, force_fetch=force_fetch)
        self.fetch_labels(gh, force_fetch=force_fetch)
        self.fetch_milestones(gh, force_fetch=force_fetch)

        if two_steps:
            self.fetch_issues(gh, force_fetch=force_fetch, state='open')
            from .tasks.repository import FirstFetchStep2
            FirstFetchStep2.add_job(self.id,
                                    force_fetch=int(force_fetch or False),
                                    gh=gh)
        else:
            self.fetch_issues(gh, force_fetch=force_fetch)
            self.fetch_comments(gh, force_fetch=force_fetch)

    def fetch_all_step2(self, gh, force_fetch=False):
        self.fetch_issues(gh, force_fetch=force_fetch, state='closed')
        self.fetch_comments(gh, force_fetch=force_fetch)


LABELTYPE_EDITMODE = Choices(
    ('LIST', 3, u'List of labels'),
    ('FORMAT', 2, u'Simple format'),
    ('REGEX', 1, u'Regular expression'),
)


class LabelType(models.Model):
    repository = models.ForeignKey(Repository, related_name='label_types')
    regex = models.TextField(
        help_text='Must contain at least this part: (?P<label>visible-part-of-the-label)", and can include "(?P<order>\d+)" for ordering',
        validators=[
            validators.RegexValidator(re.compile('\(\?\P<label>.+\)'), 'Must contain a "label" part: "(?P<label>visible-part-of-the-label)"', 'no-label'),
            validators.RegexValidator(re.compile('^(?!.*\(\?P<order>(?!\\\d\+\))).*$'), 'If an order is present, it must math a number: the exact part must be: "(?P<order>\d+)"', 'invalid-order'),
        ]
    )
    name = models.CharField(max_length=250, db_index=True)
    edit_mode = models.PositiveSmallIntegerField(choices=LABELTYPE_EDITMODE.CHOICES, default=LABELTYPE_EDITMODE.REGEX)
    edit_details = JSONField(blank=True, null=True)

    objects = LabelTypeManager()

    class Meta:
        verbose_name = u'Group'
        unique_together = (
            ('repository', 'name'),
        )
        ordering = ('name', )

    def __unicode__(self):
        return u'%s' % self.name

    def __str__(self):
        return unicode(self).encode('utf-8')

    @property
    def r(self):
        if not hasattr(self, '_regex'):
            self._regex = re.compile(self.regex)
        return self._regex

    def match(self, name):
        return self.r.search(name)

    def get_name_and_order(self, name):
        d = self.match(name).groupdict()
        return d['label'], d.get('order', None)

    def save(self, *args, **kwargs):
        """
        Check validity, save the label-type, and apply label-type search for
        all labels of the repository
        """

        # validate that the regex is ok
        self.clean_fields()

        # clear the cached compiled regex
        if hasattr(self, '_regex'):
            del self._regex

        super(LabelType, self).save(*args, **kwargs)

        # reset the cache for this label, for all names
        LabelType.objects._reset_cache(self.repository)

        # update all labels for the repository
        for label in self.repository.labels.all():
            label.save()

    def delete(self, *args, **kwargs):
        LabelType.objects._reset_cache(self.repository)
        super(LabelType, self).delete(*args, **kwargs)


class Label(GithubObject):
    repository = models.ForeignKey(Repository, related_name='labels')
    name = models.TextField()
    color = models.CharField(max_length=6)
    api_url = models.TextField(blank=True, null=True)
    label_type = models.ForeignKey(LabelType, related_name='labels', blank=True, null=True, on_delete=models.SET_NULL)
    typed_name = models.TextField(db_index=True)
    order = models.IntegerField(blank=True, null=True)

    objects = WithRepositoryManager()

    github_matching = dict(GithubObject.github_matching)
    github_matching.update({
        'url': 'api_url'
    })

    github_ignore = GithubObject.github_ignore + ('label_type', 'typed_name', )
    github_identifiers = {'repository__github_id': ('repository', 'github_id'), 'name': 'name'}
    github_edit_fields = {
        'create': ('color', 'name', ),
        'update': ('color', 'name', )
    }

    class Meta:
        unique_together = (
            ('repository', 'name'),
        )
        index_together = (
            ('repository', 'label_type', 'order'),
        )
        ordering = ('label_type', 'order', 'typed_name', )

    def __unicode__(self):
        if self.label_type_id:
            if self.order is not None:
                return u'%s: #%d %s' % (self.label_type.name, self.order, self.typed_name)
            else:
                return u'%s: %s' % (self.label_type.name, self.typed_name)
        else:
            return u'%s' % self.name

    @property
    def github_callable_identifiers(self):
        """
        If we have the api url of the label, use it as the normal way to get
        identifiers will fail since it's based on the name which may have been
        changed by the user
        """
        if self.api_url:
            return [self.api_url.replace('https://api.github.com/', '')]

        return self.repository.github_callable_identifiers_for_labels + [
            self.name,
        ]

    @property
    def github_callable_create_identifiers(self):
        return self.repository.github_callable_identifiers_for_labels

    def save(self, *args, **kwargs):
        label_type_infos = LabelType.objects.get_for_name(self.repository, self.name)
        if label_type_infos:
            self.label_type, self.typed_name, self.order = label_type_infos
        else:
            self.label_type, self.typed_name, self.order = None, self.name, None

        if kwargs.get('update_fields', None) is not None:
            kwargs['update_fields'] += ['label_type', 'typed_name', 'order']

        super(Label, self).save(*args, **kwargs)

    def fetch(self, gh, defaults=None, force_fetch=False):
        """
        Enhance the default fetch by setting the current repository as a default
        value.
        """
        if self.repository_id:
            if not defaults:
                defaults = {}
            defaults.setdefault('fk', {})['repository'] = self.repository

        return super(Label, self).fetch(gh, defaults, force_fetch=force_fetch)

    def defaults_create_values(self):
        return {'fk': {'repository': self.repository}}


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

    github_edit_fields = {
        'create': ('title', 'state', 'description', 'due_on', ),
        'update': ('title', 'state', 'description', 'due_on', )
    }

    class Meta:
        unique_together = (
            ('repository', 'number'),
        )
        ordering = ('number', )

    def __unicode__(self):
        return u'%s' % self.title

    @property
    def github_callable_identifiers(self):
        return self.repository.github_callable_identifiers_for_milestones + [
            self.number,
        ]

    @property
    def github_callable_create_identifiers(self):
        return self.repository.github_callable_identifiers_for_milestones

    def fetch(self, gh, defaults=None, force_fetch=False):
        """
        Enhance the default fetch by setting the current repository as a default
        value.
        """
        if self.repository_id:
            if not defaults:
                defaults = {}
            defaults.setdefault('fk', {})['repository'] = self.repository

        return super(Milestone, self).fetch(gh, defaults, force_fetch=force_fetch)

    def defaults_create_values(self):
        return {'fk': {'repository': self.repository}}


class Issue(GithubObjectWithId):
    repository = models.ForeignKey(Repository, related_name='issues')
    number = models.PositiveIntegerField(db_index=True)
    title = models.TextField(db_index=True)
    body = models.TextField(blank=True, null=True)
    body_html = models.TextField(blank=True, null=True)
    labels = models.ManyToManyField(Label, related_name='issues')
    user = models.ForeignKey(GithubUser, related_name='created_issues')
    assignee = models.ForeignKey(GithubUser, related_name='assigned_issues', blank=True, null=True)
    created_at = models.DateTimeField(db_index=True)
    updated_at = models.DateTimeField(db_index=True)
    closed_at = models.DateTimeField(blank=True, null=True)
    is_pull_request = models.BooleanField(default=False, db_index=True)
    milestone = models.ForeignKey(Milestone, related_name='issues', blank=True, null=True)
    state = models.CharField(max_length=10, db_index=True)
    comments_count = models.PositiveIntegerField(blank=True, null=True)
    closed_by = models.ForeignKey(GithubUser, related_name='closed_issues', blank=True, null=True)
    closed_by_fetched = models.BooleanField(default=False, db_index=True)

    comments_fetched_at = models.DateTimeField(blank=True, null=True)
    comments_etag = models.CharField(max_length=64, blank=True, null=True)

    objects = IssueManager()

    github_matching = dict(GithubObjectWithId.github_matching)
    github_matching.update({
        'comments': 'comments_count',
    })
    github_ignore = GithubObject.github_ignore + ('is_pull_request', 'comments', )
    github_format = '.full+json'
    github_edit_fields = {
        'create': ('title', 'body', 'assignee__username', 'milestone__number', 'labels__name', ),
        'update': ('title', 'body', 'assignee__username', 'state', 'milestone__number', 'labels__name', )
    }

    class Meta:
        unique_together = (
            ('repository', 'number'),
        )

    def __unicode__(self):
        return u'#%d %s' % (self.number, self.title)

    @property
    def github_callable_identifiers(self):
        return self.repository.github_callable_identifiers_for_issues + [
            self.number,
        ]

    @property
    def github_callable_create_identifiers(self):
        return self.repository.github_callable_identifiers_for_issues

    @property
    def github_callable_identifiers_for_comments(self):
        return self.github_callable_identifiers + [
            'comments',
        ]

    def fetch_comments(self, gh, force_fetch=False):
        """
        Don't fetch comments if the previous fetch of the issue told us there
        is not comments for it
        """
        if not force_fetch and self.comments_count == 0:
            return 0
        count = self._fetch_many('comments', gh,
                                defaults={'fk': {
                                    'issue': self,
                                    'repository': self.repository}
                                },
                                force_fetch=force_fetch)
        if count != self.comments_count:
            self.comments_count = count
            self.save(update_fields=('comments_count',))

        return count

    @property
    def github_callable_identifiers_for_labels(self):
        return self.github_callable_identifiers + [
            'labels',
        ]

    def fetch_labels(self, gh, force_fetch=False):
        return self._fetch_many('labels', gh,
                                defaults={'fk': {'repository': self.repository}},
                                force_fetch=force_fetch)

    @property
    def github_callable_identifiers_for_label(self, label):
        return self.github_callable_identifiers_for_labels + [
            label.name,
        ]

    def fetch_all(self, gh, force_fetch=False, **kwargs):
        super(Issue, self).fetch_all(gh, force_fetch=force_fetch)
        #self.fetch_labels(gh, force_fetch=force_fetch)  # already retrieved via self.fetch
        self.fetch_comments(gh, force_fetch=force_fetch)

    def fetch(self, gh, defaults=None, force_fetch=False):
        """
        Enhance the default fetch by setting the current repository as a default
        value.
        """
        if self.repository_id:
            if not defaults:
                defaults = {}
            defaults.setdefault('fk', {})['repository'] = self.repository

        return super(Issue, self).fetch(gh, defaults, force_fetch=force_fetch)

    def defaults_create_values(self):
        return {'fk': {'repository': self.repository}}


class IssueComment(GithubObjectWithId):
    repository = models.ForeignKey(Repository, related_name='comments')
    issue = models.ForeignKey(Issue, related_name='comments')
    user = models.ForeignKey(GithubUser, related_name='issue_comments')
    body = models.TextField(blank=True, null=True)
    body_html = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(db_index=True)
    updated_at = models.DateTimeField(db_index=True)

    objects = IssueCommentManager()

    github_format = '.full+json'
    github_edit_fields = {
        'create': ('body', ),
        'update': ('body', )
    }

    class Meta:
        ordering = ('created_at', )

    def __unicode__(self):
        return u'on issue #%d' % (self.issue.number if self.issue else '?')

    @property
    def github_callable_identifiers(self):
        return self.repository.github_callable_identifiers_for_issues + [
            'comments',
            self.github_id,
        ]

    @property
    def github_callable_create_identifiers(self):
        return self.issue.github_callable_identifiers_for_comments

    def fetch(self, gh, defaults=None, force_fetch=False):
        """
        Enhance the default fetch by setting the current repository and issue as
        default values.
        """
        if self.repository_id:
            if not defaults:
                defaults = {}
            defaults.setdefault('fk', {})['repository'] = self.repository

        if self.issue_id:
            if not defaults:
                defaults = {}
            defaults.setdefault('fk', {})['issue'] = self.issue

        return super(IssueComment, self).fetch(gh, defaults, force_fetch=force_fetch)

    def defaults_create_values(self):
        return {'fk': {
            'issue': self.issue,
            'repository': self.repository
            }
        }
