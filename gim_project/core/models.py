
from urlparse import urlsplit, parse_qs
from itertools import product
from datetime import datetime
from dateutil import tz

from django.db import models
from django.contrib.auth.models import AbstractUser

from .ghpool import parse_header_links, ApiError
from .managers import (GithubObjectManager, WithRepositoryManager,
                       IssueCommentManager, GithubUserManager, IssueManager,
                       RepositoryManager, LabelTypeManager)
import username_hack  # force the username length to be 255 chars


UTC = tz.gettz('UTC')


class GithubObject(models.Model):
    fetched_at = models.DateTimeField()

    objects = GithubObjectManager()

    github_matching = {}
    github_ignore = ()
    github_format = '+json'

    class Meta:
        abstract = True

    def __str__(self):
        return unicode(self).encode('utf-8')

    def _prepare_fetch_headers(self, if_modified_since=None, if_none_match=None):
        """
        Prepare and return the headers to use for the github call..
        """
        headers = {
            'Accept': 'application/vnd.github%s' % self.github_format
        }
        if if_modified_since:
            # tell github to retrn data only if something new
            headers['If-Modified-Since'] = if_modified_since.replace(tzinfo=UTC).strftime('%a, %d %b %Y %H:%M:%S GMT')
        if if_none_match:
            headers['If-None-Match'] = if_none_match

        return headers

    def fetch(self, auth, defaults=None, force_fetch=False):
        """
        Fetch data from github for the current object and update itself.
        If defined, "defaults" is a dict with values that will be used if not
        found in fetched data.
        """
        identifiers = self.github_callable_identifiers

        request_headers = self._prepare_fetch_headers(
                    if_modified_since=None if force_fetch else self.fetched_at)
        response_headers = {}

        try:
            obj = self.__class__.objects.get_from_github(auth, identifiers,
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

    def fetch_all(self, auth, force_fetch=False):
        """
        By default fetch only the current object. Override to add some _fetch_many
        """
        return self.fetch(auth, force_fetch=force_fetch)

    def _fetch_many(self, field_name, auth, vary=None, defaults=None, force_fetch=False):
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
        if_modified_since = None
        if_none_match = None
        if not force_fetch:
            fetched_at_field = '%s_fetched_at' % field_name
            if hasattr(self, fetched_at_field):
                # if we have a fetch date, use it
                if_modified_since = getattr(self, fetched_at_field)
                if not if_modified_since:
                    # we don't have a fetch_date, it's because we never fetched
                    # this relations, or because we set the date to None on the
                    # previous fetch because we didn't have any objects
                    if not getattr(self, field_name).count():
                        # if we don't have any objects, force a If-None-Match
                        # header that indicate "empty list", so Github won't
                        # count any requests on our rate-limit if we fetch
                        # again an empty list (and because we don't want to save
                        # etags in our db)
                        if_none_match = '"d751713988987e9331980363e24189ce"'

        request_headers = self._prepare_fetch_headers(
                    if_modified_since=if_modified_since, if_none_match=if_none_match)

        objs = []

        def fetch_page_and_next(objs, parameters):
            """
            Fetch a page of objects with the given parameters, and if github
            tell us there is a "next" page, continue fetching

            """
            response_headers = {}

            page_objs = model.objects.get_from_github(auth, identifiers,
                        defaults, parameters, request_headers, response_headers)

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

        # add per_page option
        for parameters in parameters_dicts:
            parameters.update({'per_page': 100})

        # fetch data for each combination of varying parameters
        status = {'ok': 0, 304: 0}
        restart_withouht_if_modified_since = False
        for parameters in parameters_dicts:
            try:
                fetch_page_and_next(objs, parameters)
            except ApiError, e:
                if e.response and e.response['code'] == 304:
                    # github tell us nothing is new
                    status[304] += 1
                else:
                    raise
            else:
                if status[304]:
                    # we have data but at least one time we didn't have any new
                    # one, we want to restart all without the if_modified_since
                    # header to be sure to get all data
                    restart_withouht_if_modified_since = True
                    break
                if not status['ok']:
                    # we have data despite of the if_modified_since_header, and
                    # it's the first parameter combination, we remove the header
                    # for the next combinations to be sure to get all the data
                    request_headers = self._prepare_fetch_headers(if_modified_since=None)
                status['ok'] += 1

        if restart_withouht_if_modified_since:
            # something goes wrong with the if_modified_since header and we
            # were asked to restart, so we do it without the header
            status = {'ok': 0, 304: 0}
            request_headers = self._prepare_fetch_headers(if_modified_since=None)
            objs = []
            for parameters in parameters_dicts:
                fetch_page_and_next(objs, parameters)

        # now update the list with created/updated objects
        if not status[304]:
            # but only if we had fresh data !
            self.update_related_field(field_name, [obj.id for obj in objs])

        # we return the number of fetched objects
        if not objs:
            return 0
        else:
            return len(objs)

    def update_related_field(self, field_name, ids):
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
        if to_remove:
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

        # save the fetch date
        fetched_at_field = '%s_fetched_at' % field_name
        if hasattr(self, fetched_at_field):
            save_date = True
            if not to_add:
                # If we didn't add anything, we only save a fetch_date if we have
                # data in database. On the next direct fetch, we'll use a ETAG
                # meaning "no data" to ask github if we have something new
                save_date = instance_field.count() > 0
            setattr(self, fetched_at_field, datetime.utcnow() if save_date else None)
            self.save(update_fields=[fetched_at_field], force_update=True)

        return count


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

    collaborators_fetched_at = models.DateTimeField(blank=True, null=True)
    milestones_fetched_at = models.DateTimeField(blank=True, null=True)
    labels_fetched_at = models.DateTimeField(blank=True, null=True)
    issues_fetched_at = models.DateTimeField(blank=True, null=True)
    comments_fetched_at = models.DateTimeField(blank=True, null=True)

    objects = RepositoryManager()

    class Meta:
        unique_together = (
            ('owner', 'name'),
        )

    def __unicode__(self):
        return u'%s/%s' % (self.owner.username if self.owner else '?', self.name)

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

    def fetch_collaborators(self, auth, force_fetch=False):
        return self._fetch_many('collaborators', auth, force_fetch=force_fetch)

    @property
    def github_callable_identifiers_for_labels(self):
        return self.github_callable_identifiers + [
            'labels',
        ]

    def fetch_labels(self, auth, force_fetch=False):
        return self._fetch_many('labels', auth,
                                defaults={'fk': {'repository': self}},
                                force_fetch=force_fetch)

    @property
    def github_callable_identifiers_for_milestones(self):
        return self.github_callable_identifiers + [
            'milestones',
        ]

    def fetch_milestones(self, auth, force_fetch=False):
        return self._fetch_many('milestones', auth,
                                vary={'state': ('open', 'closed')},
                                defaults={'fk': {'repository': self}},
                                force_fetch=force_fetch)

    @property
    def github_callable_identifiers_for_issues(self):
        return self.github_callable_identifiers + [
            'issues',
        ]

    def fetch_issues(self, auth, force_fetch=False):
        return self._fetch_many('issues', auth,
                                vary={'state': ('open', 'closed')},
                                defaults={'fk': {'repository': self}},
                                force_fetch=force_fetch)

    @property
    def github_callable_identifiers_for_comments(self):
        return self.github_callable_identifiers_for_issues + [
            'comments',
        ]

    def fetch_comments(self, auth, force_fetch=False):
        return self._fetch_many('comments', auth,
                                defaults={'fk': {'repository': self}},
                                force_fetch=force_fetch)

    def fetch_all(self, auth, force_fetch=False):
        super(Repository, self).fetch_all(auth, force_fetch=force_fetch)
        self.fetch_collaborators(auth, force_fetch=force_fetch)
        self.fetch_labels(auth, force_fetch=force_fetch)
        self.fetch_milestones(auth, force_fetch=force_fetch)
        self.fetch_issues(auth, force_fetch=force_fetch)
        self.fetch_comments(auth, force_fetch=force_fetch)


class LabelType(models.Model):
    repository = models.ForeignKey(Repository, related_name='label_types')
    regex = models.TextField()
    name = models.TextField(db_index=True)

    objects = LabelTypeManager()

    class Meta:
        unique_together = (
            ('repository', 'name'),
        )

    def __unicode__(self):
        return u'%s' % self.name

    def __str__(self):
        return unicode(self).encode('utf-8')

    def match(self, name):
        pass

    def get_typed_name(self, name):
        pass

    def save(self, *args, **kwargs):
        super(LabelType, self).save(*args, **kwargs)
        LabelType.objects._reset_cache(self.repository)

    def delete(self, *args, **kwargs):
        LabelType.objects._reset_cache(self.repository)
        super(LabelType, self).delete(*args, **kwargs)


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

    def __unicode__(self):
        return u'%s' % self.name

    @property
    def github_callable_identifiers(self):
        return self.repository.github_callable_identifiers_for_labels + [
            self.name,
        ]

    def save(self, *args, **kwargs):
        label_type_infos = LabelType.objects.get_for_name(self.repository, self.name)
        if label_type_infos:
            self.label_type, self.typed_name = label_type_infos
        else:
            self.typed_name = self.name

        if kwargs.get('update_fields', None) is not None:
            kwargs['update_fields'] += ['label_type', 'typed_name']

        super(Label, self).save(*args, **kwargs)

    def fetch(self, auth, defaults=None, force_fetch=False):
        """
        Enhance the default fetch by setting the current repository as a default
        value.
        """
        if self.repository_id:
            if not defaults:
                defaults = {}
            defaults.setdefault('fk', {})['repository'] = self.repository

        return super(Label, self).fetch(auth, defaults, force_fetch=force_fetch)


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

    def __unicode__(self):
        return u'#%d %s' % (self.number, self.title)

    @property
    def github_callable_identifiers(self):
        return self.repository.github_callable_identifiers_for_milestones + [
            self.number,
        ]

    def fetch(self, auth, defaults=None, force_fetch=False):
        """
        Enhance the default fetch by setting the current repository as a default
        value.
        """
        if self.repository_id:
            if not defaults:
                defaults = {}
            defaults.setdefault('fk', {})['repository'] = self.repository

        return super(Milestone, self).fetch(auth, defaults, force_fetch=force_fetch)


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
    comments_count = models.PositiveIntegerField(blank=True, null=True)

    comments_fetched_at = models.DateTimeField(blank=True, null=True)

    objects = IssueManager()

    github_matching = dict(GithubObjectWithId.github_matching)
    github_matching.update({
        'body_html': 'body',
        'comments': 'comments_count',
    })
    github_ignore = GithubObject.github_ignore + ('is_pull_request', 'comments', )
    github_format = '.html+json'

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
    def github_callable_identifiers_for_comments(self):
        return self.github_callable_identifiers + [
            'comments',
        ]

    def fetch_comments(self, auth, force_fetch=False):
        """
        Don't fetch comments if the previous fetch of the issue told us there
        is not comments for it
        """
        if not force_fetch and self.comments_count == 0:
            return 0
        return self._fetch_many('comments', auth,
                                defaults={'fk': {'issue': self}},
                                force_fetch=force_fetch)

    @property
    def github_callable_identifiers_for_labels(self):
        return self.github_callable_identifiers + [
            'labels',
        ]

    def fetch_labels(self, auth, force_fetch=False):
        return self._fetch_many('labels', auth,
                                defaults={'fk': {'repository': self.repository}},
                                force_fetch=force_fetch)

    @property
    def github_callable_identifiers_for_label(self, label):
        return self.github_callable_identifiers_for_labels + [
            label.name,
        ]

    def fetch_all(self, auth, force_fetch=False):
        super(Issue, self).fetch_all(auth, force_fetch=force_fetch)
        #self.fetch_labels(auth, force_fetch=force_fetch)  # already retrieved via self.fetch
        self.fetch_comments(auth, force_fetch=force_fetch)

    def fetch(self, auth, defaults=None, force_fetch=False):
        """
        Enhance the default fetch by setting the current repository as a default
        value.
        """
        if self.repository_id:
            if not defaults:
                defaults = {}
            defaults.setdefault('fk', {})['repository'] = self.repository

        return super(Issue, self).fetch(auth, defaults, force_fetch=force_fetch)


class IssueComment(GithubObjectWithId):
    repository = models.ForeignKey(Repository, related_name='comments')
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

    def __unicode__(self):
        return u'on issue #%d' % (self.issue.number if self.issue else '?')

    @property
    def github_callable_identifiers(self):
        return self.repository.github_callable_identifiers_for_issues + [
            'comments',
            self.github_id,
        ]

    def fetch(self, auth, defaults=None, force_fetch=False):
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

        return super(IssueComment, self).fetch(auth, defaults, force_fetch=force_fetch)
