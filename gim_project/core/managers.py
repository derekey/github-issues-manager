
import re
from datetime import datetime
from time import sleep

from django.db import models, IntegrityError
from django.contrib.auth.models import UserManager

from .ghpool import Connection, ApiError

MODE_CREATE = set(('create', ))
MODE_UPDATE = set(('update', ))
MODE_ALL = set(('create', 'update'))


class SavedObjects(dict):
    """
    A simple dict with two helpers to get/set saved objects during a fetch, to
    avoid getting/setting them many time from/to the database
    """

    def get_object(self, model, filters):
        return self[model][tuple(sorted(filters.items()))]

    def set_object(self, model, filters, obj, saved=False):
        self.setdefault(model, {})[tuple(sorted(filters.items()))] = obj


class GithubObjectManager(models.Manager):
    """
    This manager is to be used with GithubObject models.
    It provides stuff to create or update objects with json from the github api.
    """

    def ready(self):
        """
        Ignore all objects that are ready to be deleted, or created, and ones
        that failed to be created.
        To use instead of "all" when needed
        """
        return self.get_query_set().exclude(
                        github_status__in=self.model.GITHUB_STATUS_NOT_READY)

    def get_github_callable(self, gh, identifiers):
        """
        Return the github callable object for the given identifiers.
        We create it by looping through identifiers to create something like
        gh.{identiers[0].(identifiers[1])(identifiers[2])
        """
        if not identifiers:
            raise Exception('Unable to find the path to the github api.')
        result = getattr(gh, identifiers[0])
        for identifier in identifiers[1:]:
            result = result(identifier)
        return result

    def get_from_github(self, gh, identifiers, modes=MODE_ALL, defaults=None,
                        parameters=None, request_headers=None,
                        response_headers=None, min_date=None,
                        fetched_at_field='fetched_at',
                        force_update=False):
        """
        Trying to get data for the model related to this manager, by using
        identifiers to generate the API call. gh is the connection to use.
        If the min_date argument is filled, we'll only take into account object
        with the value of the field defined by github_date_field greater (only
        if you got a list from github, and we assume that the list is ordered by
        this field, descending)
        """
        data = self.get_data_from_github(
            gh=gh,
            identifiers=identifiers,
            parameters=parameters,
            request_headers=request_headers,
            response_headers=response_headers
        )
        if isinstance(data, list):
            result = self.create_or_update_from_list(data, modes, defaults,
                        min_date=min_date, fetched_at_field=fetched_at_field,
                        saved_objects=SavedObjects(), force_update=force_update)
        else:
            result = self.create_or_update_from_dict(data, modes, defaults,
                                            fetched_at_field=fetched_at_field,
                                            saved_objects=SavedObjects(),
                                            force_update=force_update,)
            if not result:
                raise Exception(
                    "Unable to create/update an object of the %s kind (modes=%s)" % (
                        self.model.__name__, ','.join(modes)))

        return result

    def get_data_from_github(self, gh, identifiers, parameters=None,
                             request_headers=None, response_headers=None):
        """
        Use the gh connection to get an object from github using the given
        identifiers
        """
        gh_callable = self.get_github_callable(gh, identifiers)
        if not parameters:
            parameters = {}
        # we'll accept some 502 errors
        tries = 0
        while tries < 5:
            try:
                return gh_callable.get(request_headers=request_headers,
                                       response_headers=response_headers,
                                       **parameters)
            except ApiError, e:
                if e.response and e.response['code'] == 502:
                    tries += 1
                    sleep(1)
                else:
                    raise

    def get_matching_field(self, field_name):
        """
        Use the github_matching attribute of the model to return the field to
        populate for a given json field.
        If no matching found, return the same field.
        """
        return self.model.github_matching.get(field_name, field_name)

    def create_or_update_from_list(self, data, modes=MODE_ALL, defaults=None,
                                min_date=None, fetched_at_field='fetched_at',
                                saved_objects=None, force_update=False):
        """
        Take a list of json objects, call create_or_update for each one, and
        return the list of touched objects. Objects that cannot be created are
        not returned.
        """
        if saved_objects is None:
            saved_objects = SavedObjects()

        objs = []
        for entry in data:
            obj = self.create_or_update_from_dict(entry, modes, defaults,
                                fetched_at_field, saved_objects, force_update)
            if obj:
                objs.append(obj)
                if min_date and obj.github_date_field:
                    obj_min_date = getattr(obj, obj.github_date_field[0])
                    if obj_min_date and obj_min_date < min_date:
                        break
        return objs

    def get_filters_from_identifiers(self, fields, identifiers=None):
        """
        Return the filters to use as argument to a Queryset to retrieve an
        object based on some identifiers.
        See get_from_identifiers for more details
        """
        filters = {}
        if not identifiers:
            identifiers = self.model.github_identifiers
        for field, lookup in identifiers.items():
            if isinstance(lookup, (tuple, list)):
                filters[field] = getattr(fields['fk'][lookup[0]], lookup[1])
            else:
                filters[field] = fields['simple'][lookup]
        return filters

    def get_from_identifiers(self, fields, identifiers=None, saved_objects=None):
        """
        Try to load an existing object from the given fields, using the
        github_identifiers attribute of the model.
        This attribute is a dict, with the left part of the queryset filter as
        key, and the right part as value. If this value is a tuple, we consider
        that this filter entry is for a FK, using the first part for the fk, and
        the right part for the fk's field.
        Return a tuple with, first, the object, or None if no objbect found for
        the given fields, and then a Boolean, set to True if the object was
        found in the saved_objects argument, else False
        If identifiers is given, use it instead of the default one from the model
        """
        if saved_objects is None:
            saved_objects = SavedObjects()

        filters = self.get_filters_from_identifiers(fields, identifiers)

        try:
            return saved_objects.get_object(self.model, filters), True
        except KeyError:
            pass
        try:
            obj = self.get(**filters)
            saved_objects.set_object(self.model, filters, obj)
            return obj, False
        except self.model.DoesNotExist:
            return None, False

    def create_or_update_from_dict(self, data, modes=MODE_ALL, defaults=None,
                            fetched_at_field='fetched_at', saved_objects=None,
                            force_update=False):
        """
        Taking a dict (passed in the data argument), try to update an existing
        object that match some fields, or create a new one.
        Return the object, or None if no object could be updated/created.
        """
        fields = self.get_object_fields_from_dict(data, defaults, saved_objects)
        if not fields:
            return None

        if saved_objects is None:
            saved_objects = SavedObjects()

        def _create_or_update(obj=None):
            # get or create a new object
            to_create = False
            if not obj:
                obj, already_saved = self.get_from_identifiers(fields, saved_objects=saved_objects)
            if not obj:
                if 'create' not in modes:
                    return None, False
                to_create = True
                obj = self.model()
            else:
                if 'update' not in modes:
                    return None, False
                # don't update object with old data
                if not force_update:
                    updated_at = getattr(obj, 'updated_at', None)
                    if updated_at:
                        new_updated_at = fields['simple'].get('updated_at')
                        if new_updated_at and new_updated_at < updated_at:
                            if not already_saved:
                                saved_objects.set_object(self.model, self.get_filters_from_identifiers(fields), obj)
                            return obj, True
                if already_saved:
                    return obj, True

            updated_fields = []

            # store simple fields if needed
            save_simples = False
            if fields['simple']:
                save_simples = True

                if not to_create:
                    obj_fields = dict((f, getattr(obj, f)) for f in fields['simple'])
                    save_simples = obj_fields != fields['simple']

                if save_simples:
                    for field, value in fields['simple'].iteritems():
                        if not hasattr(obj, field):
                            continue
                        updated_fields.append(field)
                        setattr(obj, field, value)

            # store FKs if needed
            save_fks = False
            if fields['fk']:
                save_fks = True

                if not to_create:
                    obj_fields = dict((f, getattr(obj, '%s_id' % f)) for f in fields['fk'] if hasattr(obj, '%s_id' % f))
                    fk_fields = dict((f, fields['fk'][f].id if fields['fk'][f] else None) for f in fields['fk'])
                    save_fks = obj_fields != fk_fields

                for field, value in fields['fk'].iteritems():
                    if not hasattr(obj, '%s_id' % field):
                        continue
                    if save_fks:
                        # do not set None FKs if not allowed
                        if value is None and not obj._meta.get_field(field).null:
                            continue
                        updated_fields.append(field)
                        setattr(obj, field, value)
                    # fill the django cache for FKs
                    if value and not isinstance(value, (int, long, basestring)):
                        setattr(obj, '_%s_cache' % field, value)

            # always update these two fields
            setattr(obj, fetched_at_field, datetime.utcnow())
            obj.github_status = obj.GITHUB_STATUS_CHOICES.FETCHED

            # force update or insert to avoid a exists() call in db
            if to_create:
                save_params = {'force_insert': True}
            else:
                save_params = {
                    'force_update': True,
                    # only save updated fields
                    'update_fields': updated_fields + [fetched_at_field,
                                                       'github_status'],
                }

            obj.save(**save_params)

            return obj, False

        obj, already_saved = _create_or_update()

        if not obj:
            return None

        if already_saved:
            return obj

        # finally save lists now that we have an object
        for field, values in fields['many'].iteritems():
            obj.update_related_field(field, [o.id for o in values])

        # save object in the cache
        saved_objects.set_object(self.model, self.get_filters_from_identifiers(fields), obj)

        return obj

    def get_object_fields_from_dict(self, data, defaults=None, saved_objects=None):
        """
        Taking a dict (passed in the data argument), return the fields to use
        to update or create an object. The returned dict contains 3 entries:
            - 'simple' to hold values for simple fields
            - 'fk' to hold values (real model instances) for foreign keys
            - 'many' to hold list of real model instances for many to many fields
              or for the related relation of a fk (issues of a repository...)
        Eeach of these entries is a dict with the model field names as key, and
        the values to save in the model as value.
        The "defaults" arguments is to fill fields not found in data. It must
        respect the same format as the return of this method: a dict with
        "simple"/"fk"/"many" as keys, with a dict of fields as values. A
        "related" entry can be present for default values to use for related
        data (if "foo" is a related found in "data", defaults["related"]["foo"]
        will be the "defaults" dict used to create/update "foo)
        """

        # reduce data to keep only wanted fields
        for key in data.keys():
            if key.startswith('_') or \
                key.endswith('etag') or \
                key.endswith('fetched_at') or \
                key in self.model.github_ignore:
                del data[key]

        if saved_objects is None:
            saved_objects = SavedObjects()

        fields = {
            'simple': {},
            'fk': {},
            'many': {}
        }

        # run for each field in the dict
        for key, value in data.iteritems():

            # maybe we use a different field name on our side
            field_name = self.get_matching_field(key)

            try:
                # get informations about the field
                field, _, direct, is_m2m = self.model._meta.get_field_by_name(field_name)
            except models.FieldDoesNotExist:
                # there is not field for the given key, we pass to the next key
                continue

            # work depending of the field type
            # TODO: nanage OneToOneField, not yet used in our models
            if is_m2m or not direct or isinstance(field, models.ForeignKey):
                # we have many objects to create: m2m
                # or we have an external object to create: fk
                if value:
                    model = field.related.parent_model if direct else field.model
                    defaults_related = {}

                    if defaults and 'related' in defaults:
                        if field_name in defaults['related']:
                            defaults_related = defaults['related'][field_name]
                        elif field_name in defaults['related'].get('*', {}):
                            defaults_related = defaults['related']['*'][field_name]
                        if '*' in defaults['related'] and '*' not in defaults_related:
                            defaults_related.update(defaults['related']['*'])

                    if is_m2m or not direct:  # not sure: a list for a "not direct ?" (a through ?)
                        fields['many'][field_name] = model.objects\
                            .create_or_update_from_list(data=value,
                                                        defaults=defaults_related,
                                                        saved_objects=saved_objects)
                    else:
                        fields['fk'][field_name] = model.objects\
                            .create_or_update_from_dict(data=value,
                                                        defaults=defaults_related,
                                                        saved_objects=saved_objects)
                else:
                    if is_m2m or not direct:
                        fields['many'][field_name] = []
                    else:
                        fields['fk'][field_name] = None

            elif isinstance(field, models.DateTimeField):
                # we need to convert a datetimefield
                if value:
                    # all github datetime are utc, so we can remove the timezome
                    fields['simple'][field_name] = Connection.parse_date(value)
                else:
                    fields['simple'][field_name] = None

            else:
                # it's a simple field
                fields['simple'][field_name] = value

        # add default fields
        if defaults:
            for field_type, default_fields in defaults.iteritems():
                if field_type not in ('simple', 'fk', 'many'):
                    continue
                for field_name, value in default_fields.iteritems():
                    if field_name not in fields[field_type]:
                        fields[field_type][field_name] = value

        return fields


class WithRepositoryManager(GithubObjectManager):
    """
    This manager si to be used for models based on GithubObject which have a
    repository field that is a FK toward the Repository model.
    The get_object_fields_from_dict is enhance to find the matching repository
    based on the url field from github in case of github don't tell us to which
    repository belongs the object.
    """

    def get_object_fields_from_dict(self, data, defaults=None, saved_objects=None):
        """
        In addition to the default get_object_fields_from_dict, try to guess the
        repository the objects belongs to, from the url found in the data given
        by the github api. Only set if the repository is found.
        """
        from .models import Repository

        url = data.get('url')

        fields = super(WithRepositoryManager, self).get_object_fields_from_dict(
                                                data, defaults, saved_objects)
        if not fields:
            return None

        # add the repository if needed
        if not fields['fk'].get('repository'):
            if url:
                repository = Repository.objects.get_by_url(url)
                if repository:
                    fields['fk']['repository'] = repository
            if not fields['fk'].get('repository'):
                # no repository found, don't save the object !
                return None

        return fields


class GithubUserManager(GithubObjectManager, UserManager):
    """
    This manager is for the GithubUser model, and is based on the default
    UserManager, and the GithubObjectManager to allow creation/update from data
    coming from the github api.
    The get_object_fields_from_dict is enhance to compute the is_organization
    flag.
    """

    def get_object_fields_from_dict(self, data, defaults=None, saved_objects=None):
        """
        In addition to the default get_object_fields_from_dict, set the
        is_organization flag based on the value of the User field given by the
        github api.
        """

        is_org = data.get('type', 'User') == 'Organization'

        fields = super(GithubUserManager, self).get_object_fields_from_dict(
                                                data, defaults, saved_objects)
        if not fields:
            return None

        # add the is_organization field if needed
        if 'is_organization' not in fields['simple']:
            fields['simple']['is_organization'] = is_org

        return fields

    def get_deleted_user(self):
        """
        Return a user to use when the github api doesn't give us a user when
        we really need one
        """
        if not hasattr(self, '_deleted_user'):
            self._deleted_user, created = self.get_or_create(username='user.deleted')
        return self._deleted_user


class RepositoryManager(GithubObjectManager):
    """
    This manager extends the GithubObjectManager with helpers to find a
    repository based on an url or simply a path ({user}/{repos}).
    """
    path_finder = re.compile('^https?://api\.github\.com/repos/(?P<path>[^/]+/[^/]+)(?:/|$)')

    def get_path_from_url(self, url):
        """
        Taking an url, try to return the path ({user}/{repos}) of a repository,
        or None.
        """
        if not url:
            return None
        match = self.path_finder.match(url)
        if not match:
            return None
        return match.groupdict().get('path', None)

    def get_by_path(self, path):
        """
        Taking a path ({user}/{repos}), try to return the matching repository,
        or None if no one is found.
        """
        if not path:
            return None
        try:
            username, name = path.split('/')
        except ValueError:
            return None
        else:
            try:
                return self.get(owner__username=username, name=name)
            except self.model.DoesNotExist:
                return None

    def get_by_url(self, url):
        """
        Taking an url, try to return the matching repository by finding the path
        ({user}/{repos}) from the url and fetching from the db.
        Return None if no path or no matching repository found.
        """
        path = self.get_path_from_url(url)
        return self.get_by_path(path)


class IssueManager(WithRepositoryManager):
    """
    This manager extends the GithubObjectManager with helpers to find an
    issue based on an url or simply a path+number ({user}/{repos}/issues/{number}).
    It also provides an enhanced get_object_fields_from_dict method, to compute the
    is_pull_request flag, and set default values for labels and milestone
    repository.
    """
    issue_finder = re.compile('^https?://api\.github\.com/repos/(?:[^/]+/[^/]+)/(?:issues|pulls)/(?P<number>\w+)(?:/|$)')

    def get_number_from_url(self, url):
        """
        Taking an url, try to return the number of an issue, or None.
        """
        if not url:
            return None
        match = self.issue_finder.match(url)
        if not match:
            return None
        return match.groupdict().get('number', None)

    def get_by_repository_and_number(self, repository, number):
        """
        Taking a repository instance and an issue number, try to return the
        matching issue. or None if no one is found.
        """
        if not repository or not number:
            return None
        try:
            return self.get(repository_id=repository.id, number=number)
        except self.model.DoesNotExist:
            return None

    def get_by_url(self, url, repository=None):
        """
        Taking an url, try to return the matching issue by finding the repository
        by its path, and an issue number, and then fetching the issue from the db.
        Return None if no Issue if found.
        """
        if not repository:
            from .models import Repository
            repository = Repository.objects.get_by_url(url)
        if not repository:
            return None
        number = self.get_number_from_url(url)
        return self.get_by_repository_and_number(repository, number)

    def get_object_fields_from_dict(self, data, defaults=None, saved_objects=None):
        """
        Override the default "get_object_fields_from_dict" by adding default
        value for the repository of labels, milestone and comments, if one is
        given as default for the issue.
        Also set the is_pull_request flag based on the 'diff_url' attribute of
        the 'pull_request' dict in the data given by the github api.
        If we have data from the pull-requests API (instead of the issues one),
        we also remove the github_id from the fields to avoid replacing it in
        the existing issue (note that github have different ids for a pull
        request and its associated issue, and that when fetching pull requests,
        we only do UPDATE, no CREATE)
        We also move some fields from sub-dicts to the main one to easy access
        (base and head sha/label in pull-request mode)

        """
        # if pull request, we may have the label and sha of base and head
        for boundary in ('base', 'head'):
            dikt = data.get(boundary, {})
            for field in ('label', 'sha'):
                if dikt.get(field):
                    data['%s_%s' % (boundary, field)] = dikt[field]

        try:
            is_pull_request = defaults['simple']['is_pull_request']
        except KeyError:
            is_pull_request = bool(data.get('diff_url', False))\
                   or bool(data.get('pull_request', {}).get('diff_url', False))

        fields = super(IssueManager, self).get_object_fields_from_dict(
                                                data, defaults, saved_objects)
        if not fields:
            return None

        # check if it's a pull request
        if 'is_pull_request' not in fields['simple']:
            fields['simple']['is_pull_request'] = is_pull_request

        # if we have a real pull request data (from the pull requests api instead
        # of the issues one), remove the github_id to not override the issue's one
        # but save it in github_pr_id
        if fields['simple'].get('head_sha') or fields['simple'].get('base_sha'):
            if 'github_id' in fields['simple']:
                fields['simple']['github_pr_id'] = fields['simple']['github_id']
                del fields['simple']['github_id']

        # when we fetch lists, mergeable status are not set, so we remove them from
        # fields to update to avoid losing previous values
        # if 'mergeable' in fields['simple']:
        if 'mergeable' in fields['simple'] and fields['simple']['mergeable'] is None:
            del fields['simple']['mergeable']
        if 'mergeable_state' in fields['simple'] and fields['simple']['mergeable_state'] in (None, 'unknown'):
            del fields['simple']['mergeable_state']

        # idem for "merged"
        if 'merged' in fields['simple'] and fields['simple']['merged'] is None:
            del fields['simple']['merged']

        return fields


class WithIssueManager(GithubObjectManager):
    """
    This base manager is for the models linked to an issue, with an enhanced
    get_object_fields_from_dict method, to get the issue and the repository.
    """

    def get_object_fields_from_dict(self, data, defaults=None, saved_objects=None):
        """
        In addition to the default get_object_fields_from_dict, try to guess the
        issue the object belongs to, from the issue_url found in the data given
        by the github api. Doing the same for the repository. Only set if found.
        """
        from .models import Issue

        url = data.get('issue_url', data.get('pull_request_url'))

        fields = super(WithIssueManager, self).get_object_fields_from_dict(
                                                data, defaults, saved_objects)
        if not fields:
            return None

        repository = fields['fk'].get('repository')

        # add the issue if needed
        if not fields['fk'].get('issue'):
            if url:
                issue = Issue.objects.get_by_url(url, repository)
                if issue:
                    fields['fk']['issue'] = issue

            if not fields['fk'].get('issue'):
                # no issue found, don't save the object !
                return None

        # and the repository
        if not repository:
            fields['fk']['repository'] = fields['fk']['issue'].repository

        return fields


class IssueCommentManager(WithIssueManager):
    """
    This manager is for the IssueComment model, with an enhanced
    get_object_fields_from_dict method (from WithIssueManager), to get the issue
    and the repository.
    """
    pass


class LabelTypeManager(models.Manager):
    """
    This manager, for the LabelType model, manage a cache by repository/label-name
    to quickly return label type and typed name for a label.
    """
    _name_cache = {}
    AUTO_TYPE_FIND_RE = re.compile(r'^(.*)(\s*):(\s*)(.*)$')
    AUTO_TYPE_FORMAT = '%s%s:%s{label}'

    def _reset_cache(self, repository):
        """
        Clear all the cache for the given repository
        """
        self._name_cache.pop(repository.id, None)

    def get_for_name(self, repository, name):
        """
        Return the label_type and typed_name to use for a label in a repository.
        Use an internal cache to speed up future accesses.
        """
        if repository.id not in self._name_cache:
            self._name_cache[repository.id] = {}

        if name not in self._name_cache[repository.id]:
            found_label_type = None

            # search an existing label type
            for label_type in repository.label_types.all():
                if label_type.match(name):
                    found_label_type = label_type
                    break

            # try to add an automatic group
            if found_label_type is None:
                match = self.AUTO_TYPE_FIND_RE.match(name)
                if match:
                    type_name, spaces1, spaces2, label = match.groups()
                    format_string = self.AUTO_TYPE_FORMAT % (type_name, spaces1, spaces2)
                    found_label_type = repository.label_types.create(
                        name=type_name.capitalize(),
                        edit_mode=self.model.LABELTYPE_EDITMODE.FORMAT,
                        edit_details={'format_string': format_string},
                        regex=self.model.regex_from_format(format_string)
                    )

            result = None
            if found_label_type:
                name, order = found_label_type.get_name_and_order(name)
                result = (
                    found_label_type,
                    name,
                    int(order) if order is not None else None,
                )

            self._name_cache[repository.id][name] = result

        return self._name_cache[repository.id][name]


class PullRequestCommentManager(WithIssueManager):
    """
    This manager is for the PullRequestComment model, with an enhanced
    get_object_fields_from_dict method to get the issue, the repository, and
    the entry point
    """

    def get_object_fields_from_dict(self, data, defaults=None, saved_objects=None):
        """
        In addition to the default get_object_fields_from_dict, try to guess the
        issue the comment belongs to, from the pull_request_url found in the
        data given by the github api. Doing the same for the repository.
        Only set if found.
        Also get/create the entry_point: some fetched data are for the entry
        point, some others are for the comment)
        """
        from .models import PullRequestCommentEntryPoint

        fields = super(PullRequestCommentManager, self).get_object_fields_from_dict(
                                                data, defaults, saved_objects)

        if not fields:
            return None

        defaults_entry_points = {
            'fk': {
                'repository': fields['fk']['repository'],
                'issue': fields['fk']['issue'],
            }
        }

        entry_point = PullRequestCommentEntryPoint.objects\
                    .create_or_update_from_dict(data=data,
                                                defaults=defaults_entry_points,
                                                saved_objects=saved_objects)
        if entry_point:
            fields['fk']['entry_point'] = entry_point

        return fields


class PullRequestCommentEntryPointManager(GithubObjectManager):
    """
    This manager is for the PullRequestCommentEntryPoint model, with an
    enhanced create_or_update_from_dict that will save the created_at (oldest
    from the comments) and updated_at (latest from the comments).
    Also save the user if it's the first one.
    """

    def create_or_update_from_dict(self, data, modes=MODE_ALL, defaults=None,
                            fetched_at_field='fetched_at', saved_objects=None,
                                                            force_update=False):
        from .models import GithubUser

        try:
            created_at = Connection.parse_date(data['created_at'])
        except Exception:
            created_at = None
        try:
            updated_at = Connection.parse_date(data['updated_at'])
        except Exception:
            updated_at = None

        user = data.get('user')

        obj = super(PullRequestCommentEntryPointManager, self)\
            .create_or_update_from_dict(data, modes, defaults, fetched_at_field,
                                                    saved_objects, force_update)

        if not obj:
            return None

        update_fields = []

        if created_at and (not obj.created_at or created_at < obj.created_at):
            obj.created_at = created_at
            update_fields.append('created_at')
            if user:
                obj.user = GithubUser.objects.create_or_update_from_dict(
                                            user, saved_objects=saved_objects)
                update_fields.append('user')

        if updated_at and (not obj.updated_at or updated_at > obj.updated_at):
            obj.updated_at = updated_at
            update_fields.append('updated_at')

        if update_fields:
            obj.save(update_fields=update_fields)

        return obj


class CommitManager(WithRepositoryManager):
    """
    This manager is for the Commit model, with an enhanced
    get_object_fields_from_dict method, to get the issue and the repository,
    and to reformat data in a flat way to match the model.
    """

    def get_object_fields_from_dict(self, data, defaults=None, saved_objects=None):
        """
        Reformat data to have flat values to match the model
        """
        if 'commit' in data:
            c = data['commit']
            if 'message' in c:
                data['message'] = c['message']
            for user_type, date_field in (('author', 'authored'), ('committer', 'committed')):
                if user_type in c:
                    if 'date' in c[user_type]:
                        data['%s_at' % date_field] = c[user_type]['date']
                    for field in ('email', 'name'):
                        if field in c[user_type]:
                            data['%s_%s' % (user_type, field)] = c[user_type][field]
            if 'tree' in c:
                data['tree'] = c['tree']['sha']

        return super(CommitManager, self).get_object_fields_from_dict(
                                                data, defaults, saved_objects)


class IssueEventManager(WithIssueManager):
    """
    This manager is for the IssueEvent model, with method to check references
    in other objects and create events for found references.
    """

    CHECK_REF = re.compile(r'(?:^|\W)#(\d+)(?:[^d]|$)')

    def check_references(self, obj, fields, user_field='user'):
        """
        Check if the given object has references to some issues in its text.
        The references are looked up from given fields of the object, using
        the CHECK_REF regex of the manager.
        An IssueEvent object is created for each reference.
        Once done for the object, existing events that do not apply anymore are
        removed.
        """
        from core.models import Issue

        type_event = 'referenced_by_%s' % obj._meta.module_name

        existing_events_ids = obj.repository.issues_events.filter(
                                                    event=type_event,
                                                    related_object_id=obj.id
                                                ).values_list('id', flat=True)

        new_events_ids = set()
        for field in fields:
            val = getattr(obj, field)
            if not val:
                continue
            for number in self.CHECK_REF.findall(val):
                try:
                    issue = obj.repository.issues.get(number=number)
                except Issue.DoesNotExist:
                    break

                event, created = self.get_or_create(
                                    repository=obj.repository,
                                    issue=issue,
                                    event=type_event,
                                    related_object_id=obj.id,
                                    defaults={
                                        'user': getattr(obj, user_field),
                                        'created_at': obj.created_at,
                                        'related_object': obj,
                                    }
                                )
                new_events_ids.add(event.id)

        # remove old events
        for existing_event_id in existing_events_ids:
            if existing_event_id not in new_events_ids:
                try:
                    self.get(id=existing_event_id).delete()
                except self.model.DoesNotExist:
                    pass

        return new_events_ids


class PullRequestFileManager(WithIssueManager):
    tree_finder = re.compile('^https?://github\.com/(?:[^/]+/[^/]+)/blob/(?P<tree>[^/]+)')

    def get_tree_in_url(self, url):
        """
        Taking an url, try to return the tree sha
        """
        if not url:
            return None
        match = self.tree_finder.match(url)
        if not match:
            return None
        return match.groupdict().get('tree', None)

    def get_object_fields_from_dict(self, data, defaults=None, saved_objects=None):
        """
        Set in data the tree got from the blob url
        """
        if 'blob_url' in data:
            data['tree'] = self.get_tree_in_url(data['blob_url'])

        return super(PullRequestFileManager, self).get_object_fields_from_dict(
                                                data, defaults, saved_objects)


class AvailableRepositoryManager(WithRepositoryManager):
    def get_object_fields_from_dict(self, data, defaults=None, saved_objects=None):
        """
        We have a dict which is repositories, with a "permissions" field, but we
        want a dict with a repository dict and a "permission" field which is
        normalized from the "permissions" one.
        """
        permission = None

        if 'permissions' in data:
            for perm in ('admin', 'push', 'pull'):  # order is important: higher permission first
                if data['permissions'].get(perm):
                    permission = perm
                    break

        return super(AvailableRepositoryManager, self).get_object_fields_from_dict(
            {'permission': permission, 'repository': data},
            defaults, saved_objects)
