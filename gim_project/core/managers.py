
import re
from datetime import datetime

from django.db import models, IntegrityError
from django.contrib.auth.models import UserManager

from .ghpool import Connection

MODE_CREATE = set(('create', ))
MODE_UPDATE = set(('update', ))
MODE_ALLS = set(('create', 'update'))


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
                github_status__in=(
                            self.model.GITHUB_STATUS_CHOICES.WAITING_DELETE,
                            self.model.GITHUB_STATUS_CHOICES.WAITING_CREATE,
                            self.model.GITHUB_STATUS_CHOICES.ERROR_CREATE
                            )
                )

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

    def get_from_github(self, gh, identifiers, modes=MODE_ALLS, defaults=None,
                        parameters=None, request_headers=None,
                        response_headers=None):
        """
        Trying to get data for the model related to this manager, by using
        identifiers to generate the API call. gh is the connection to use.
        """
        data = self.get_data_from_github(
            gh=gh,
            identifiers=identifiers,
            parameters=parameters,
            request_headers=request_headers,
            response_headers=response_headers
        )

        if isinstance(data, list):
            result = self.create_or_update_from_list(data, modes, defaults)
        else:
            result = self.create_or_update_from_dict(data, modes, defaults)
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
        return gh_callable.get(request_headers=request_headers,
                               response_headers=response_headers,
                               **parameters)

    def get_matching_field(self, field_name):
        """
        Use the github_matching attribute of the model to return the field to
        populate for a given json field.
        If no matching found, return the same field.
        """
        return self.model.github_matching.get(field_name, field_name)

    def create_or_update_from_list(self, data, modes=MODE_ALLS, defaults=None):
        """
        Take a list of json objects, call create_or_update for each one, and
        return the list of touched objects. Objects that cannot be created are
        not returned.
        """
        objs = []
        for entry in data:
            obj = self.create_or_update_from_dict(entry, modes, defaults)
            if obj:
                objs.append(obj)
        return objs

    def get_from_identifiers(self, fields, identifiers=None):
        """
        Try to load an existing object from the given fields, using the
        github_identifiers attribute of the model.
        This attribute is a dict, with the left part of the queryset filter as
        key, and the right part as value. If this value is a tuple, we consider
        that this filter entry is for a FK, using the first part for the fk, and
        the right part for the fk's field.
        Returns None if no object found for the given filter.
        If identifiers is given, use it instead of the default one from the model
        """
        filters = {}
        if not identifiers:
            identifiers = self.model.github_identifiers
        for field, lookup in identifiers.items():
            if isinstance(lookup, (tuple, list)):
                filters[field] = getattr(fields['fk'][lookup[0]], lookup[1])
            else:
                filters[field] = fields['simple'][lookup]
        try:
            return self.get(**filters)
        except self.model.DoesNotExist:
            return None

    def create_or_update_from_dict(self, data, modes=MODE_ALLS, defaults=None):
        """
        Taking a dict (passed in the data argument), try to update an existing
        object that match some fields, or create a new one.
        Return the object, or None if no object could be updated/created.
        """
        fields = self.get_object_fields_from_dict(data, defaults)

        if not fields:
            return None

        def _create_or_update():
            # get or create a new object
            to_create = False
            obj = self.get_from_identifiers(fields)
            if not obj:
                if 'create' not in modes:
                    return None
                to_create = True
                obj = self.model()
            elif 'update' not in modes:
                return None

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
                        updated_fields.append(field)
                        setattr(obj, field, value)

            # store FKs if needed
            save_fks = False
            if fields['fk']:
                save_fks = True

                if not to_create:
                    obj_fields = dict((f, getattr(obj, '%s_id' % f)) for f in fields['fk'])
                    fk_fields = dict((f, fields['fk'][f].id if fields['fk'][f] else None) for f in fields['fk'])
                    save_fks = obj_fields != fk_fields

                if save_fks:
                    for field, value in fields['fk'].iteritems():
                        updated_fields.append(field)
                        setattr(obj, field, value)

            # always update these two fields
            obj.fetched_at = datetime.utcnow()
            obj.github_status = obj.GITHUB_STATUS_CHOICES.FETCHED

            try:
                # force update or insert to avoid a exists() call in db
                if to_create:
                    save_params = {'force_insert': True}
                else:
                    save_params = {
                        'force_update': True,
                        # only save updated fields
                        'update_fields': updated_fields + ['fetched_at', 'github_status'],
                    }

                obj.save(**save_params)

            except IntegrityError:
                # We could have an integrity error if we tried to create an
                # object that has been created elsewhere during the process
                # So we check if we really have an object now, and retry the
                # whole set/save process.
                # If we already have an object in db, or if we haven't but there
                # is still no object, it's a real IntegrityError that we don't
                # want to skip
                if to_create:
                    obj = self.get_from_identifiers(fields)
                    if obj:
                        return _create_or_update()
                    else:
                        raise
                else:
                    raise

            return obj

        obj = _create_or_update()

        if not obj:
            return None

        # finally save lists now that we have an object
        for field, values in fields['many'].iteritems():
            obj.update_related_field(field, [o.id for o in values])

        return obj

    def get_object_fields_from_dict(self, data, defaults=None):
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

        fields = {
            'simple': {},
            'fk': {},
            'many': {}
        }

        # run for each field in the dict
        for key, value in data.iteritems():

            # maybe we use a different field name on our side
            field_name = self.get_matching_field(key)

            # ignore forbidden fields
            if field_name in self.model.github_ignore:
                continue

            try:
                # get informations about the field
                field, _, direct, is_m2m = self.model._meta.get_field_by_name(field_name)
            except models.FieldDoesNotExist:
                # there is not field for the given key, we pass to the next key
                continue

            # work depending of the field type
            # TODO: nanage OneToOneField, not yet used in our models
            if is_m2m or not direct:
                # we have many objects to create
                if value:
                    model = field.related.parent_model if direct else field.model
                    defaults_related = None
                    if defaults and 'related' in defaults and field_name in defaults['related']:
                        defaults_related = defaults['related'][field_name]
                    fields['many'][field_name] = model.objects\
                        .create_or_update_from_list(data=value,
                                                    defaults=defaults_related)
                else:
                    fields['many'][field_name] = []

            elif isinstance(field, models.ForeignKey):
                # we have an external object to create
                if value:
                    model = field.related.parent_model if direct else field.model
                    defaults_related = None
                    if defaults and 'related' in defaults and field_name in defaults['related']:
                        defaults_related = defaults['related'][field_name]
                    fields['fk'][field_name] = model.objects\
                        .create_or_update_from_dict(data=value,
                                                    defaults=defaults_related)
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

    def get_object_fields_from_dict(self, data, defaults=None):
        """
        In addition to the default get_object_fields_from_dict, try to guess the
        repository the objects belongs to, from the url found in the data given
        by the github api. Only set if the repository is found.
        """
        from .models import Repository

        fields = super(WithRepositoryManager, self).get_object_fields_from_dict(data, defaults)
        if not fields:
            return None

        # add the repository if needed
        if 'repository' not in fields['fk']:
            repository = Repository.objects.get_by_url(data.get('url', None))
            if repository:
                fields['fk']['repository'] = repository
            else:
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

    def get_object_fields_from_dict(self, data, defaults=None):
        """
        In addition to the default get_object_fields_from_dict, set the
        is_organization flag based on the value of the User field given by the
        github api.
        """
        fields = super(GithubUserManager, self).get_object_fields_from_dict(data, defaults)
        if not fields:
            return None

        # add the is_organization field if needed
        if 'is_organization' not in fields['simple']:
            fields['simple']['is_organization'] = data.get('type', 'User') == 'Organization'

        return fields


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

    def get_by_url(self, url):
        """
        Taking an url, try to return the matching issue by finding the repository
        by its path, and an issue number, and then fetching the issue from the db.
        Return None if no Issue if found.
        """
        from .models import Repository
        repository = Repository.objects.get_by_url(url)
        if not repository:
            return None
        number = self.get_number_from_url(url)
        return self.get_by_repository_and_number(repository, number)

    def get_object_fields_from_dict(self, data, defaults=None):
        """
        Override the default "get_object_fields_from_dict" by adding default
        value for the repository of labels, milestone and comments, if one is
        given as default for the issue.
        Also set the is_pull_request flag based on the 'diff_url' attribute of
        the 'pull_request' dict in the data given by the github api.
        """
        if defaults and 'fk' in defaults and 'repository' in defaults['fk']:
            if 'related' not in defaults:
                defaults['related'] = {}
            for related in ('labels', 'milestone', 'comments', 'pr_comments'):
                if related not in defaults['related']:
                    defaults['related'][related] = {}
                if 'fk' not in defaults['related'][related]:
                    defaults['related'][related]['fk'] = {}
                defaults['related'][related]['fk']['repository'] = defaults['fk']['repository']

        fields = super(IssueManager, self).get_object_fields_from_dict(data, defaults)
        if not fields:
            return None

        # check if it's a pull request
        if 'is_pull_reques' not in fields['simple']:
            fields['simple']['is_pull_request'] = bool(data.get('pull_request', {}).get('diff_url', False))

        return fields


class IssueCommentManager(GithubObjectManager):
    """
    This manager is for the IssueComment model, with an enhanced
    get_object_fields_from_dict method, to get the issue and the repository.
    """

    def get_object_fields_from_dict(self, data, defaults=None):
        """
        In addition to the default get_object_fields_from_dict, try to guess the
        issue the comment belongs to, from the issue_url found in the data given
        by the github api. Doing the same for the repository. Only set if found.
        """
        from .models import Issue

        fields = super(IssueCommentManager, self).get_object_fields_from_dict(data, defaults)
        if not fields:
            return None

        # add the issue if needed
        if 'issue' not in fields['fk']:
            issue = Issue.objects.get_by_url(data.get('issue_url', None))
            if issue:
                fields['fk']['issue'] = issue
            else:
                # no issue found, don't save the object !
                return None

        # and the repository
        if 'repository' not in fields['fk']:
            fields['fk']['repository'] = fields['fk']['issue'].repository

        return fields


class LabelTypeManager(models.Manager):
    """
    This manager, for the LabelType model, manage a cache by repository/label-name
    to quickly return label type and typed name for a label.
    """
    _name_cache = {}

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
            result = None
            for label_type in repository.label_types.all():
                if label_type.match(name):
                    name, order = label_type.get_name_and_order(name)
                    result = (
                        label_type,
                        name,
                        int(order) if order is not None else None,
                    )
                    break
            self._name_cache[repository.id][name] = result

        return self._name_cache[repository.id][name]


class PullRequestCommentManager(GithubObjectManager):
    """
    This manager is for the PullRequestComment model, with an enhanced
    get_object_fields_from_dict method to get the issue, the repository, and
    the entry point
    """

    def get_object_fields_from_dict(self, data, defaults=None):
        """
        In addition to the default get_object_fields_from_dict, try to guess the
        issue the comment belongs to, from the pull_request__url found in the
        data given by the github api. Doing the same for the repository.
        Only set if found.
        Also get/create the entry_point: some fetched data are for the entry
        point, some others are for the comment)
        """
        from .models import Issue, PullRequestCommentEntryPoint

        fields = super(PullRequestCommentManager, self).get_object_fields_from_dict(data, defaults)

        if not fields:
            return None

        # add the issue if needed
        if 'issue' not in fields['fk']:
            issue = Issue.objects.get_by_url(data.get('pull_request_url', None))
            if issue:
                fields['fk']['issue'] = issue
            else:
                # no issue found, don't save the object !
                return None

        # and the repository
        if 'repository' not in fields['fk']:
            fields['fk']['repository'] = fields['fk']['issue'].repository

        defaults_entry_points = {
            'fk': {
                'repository': fields['fk']['repository'],
                'issue': fields['fk']['issue'],
            }
        }

        entry_point = PullRequestCommentEntryPoint.objects\
                    .create_or_update_from_dict(data=data,
                                                defaults=defaults_entry_points)
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

    def create_or_update_from_dict(self, data, modes=MODE_ALLS, defaults=None):
        from .models import GithubUser

        obj = super(PullRequestCommentEntryPointManager, self)\
                            .create_or_update_from_dict(data, modes, defaults)

        if not obj:
            return None

        try:
            created_at = Connection.parse_date(data['created_at'])
        except Exception:
            created_at = None
        try:
            updated_at = Connection.parse_date(data['updated_at'])
        except Exception:
            updated_at = None

        update_fields = []

        if created_at and not obj.created_at or created_at < obj.created_at:
            obj.created_at = created_at
            update_fields.append('created_at')
            try:
                obj.user = GithubUser.objects.create_or_update_from_dict(data['user'])
                update_fields.append('user')
            except Exception:
                pass

        if updated_at and not obj.updated_at or updated_at > obj.updated_at:
            obj.updated_at = updated_at
            update_fields.append('updated_at')

        if update_fields:
            obj.save(update_fields=update_fields)

        return obj
