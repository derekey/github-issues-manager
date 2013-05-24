
import re
import dateutil.parser
from datetime import datetime

from django.db import models
from django.contrib.auth.models import UserManager

from .ghpool import Connection


class GithubObjectManager(models.Manager):
    """
    This manager is to be used with GithubObject models.
    It provides stuff to create or update objects with json from the github api.
    """

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

    def get_from_github(self, auth, identifiers, parameters=None):
        """
        Trying to get data for the model related to this manager, by using
        identifiers to generate the API call. auth is a dictionnary used to
        call Connection.get.
        """
        gh = Connection.get(**auth)

        data = self.get_data_from_github(gh, identifiers, parameters)

        if isinstance(data, list):
            result = self.create_or_update_from_list(data)
        else:
            result = self.create_or_update_from_dict(data)
            if not result:
                raise Exception("Unable to create an object of the %s kind" % self.model.__name__)

        return result

    def get_data_from_github(self, gh, identifiers, parameters):
        """
        Use the gh connection to get an object from github using the given
        identifiers
        """
        gh_callable = self.get_github_callable(gh, identifiers)
        if not parameters:
            parameters = {}
        return gh_callable.get(**parameters)

    def get_matching_field(self, field_name):
        """
        Use the github_matching attribute of the model to return the field to
        populate for a given json field.
        If no matching found, return the same field.
        """
        return self.model.github_matching.get(field_name, field_name)

    def create_or_update_from_list(self, data):
        """
        Take a list of json objects, call create_or_update for each one, and
        return the list of touched objects. Objects that cannot be created are
        not returned.
        """
        objs = []
        for entry in data:
            obj = self.create_or_update_from_dict(entry)
            if obj:
                objs.append(obj)
        return objs

    def get_from_identifiers(self, fields):
        """
        Try to load an existing object from the given fields, using the
        github_identifiers attribute of the model.
        This attribute is a dict, with the left part of the queryset filter as
        key, and the right part as value. If this value is a tuple, we consider
        that this filter entry is for a FK, using the first part for the fk, and
        the right part for the fk's field.
        Returns None if no object found for the given filter.
        """
        filters = {}
        for field, lookup in self.model.github_identifiers.items():
            if isinstance(lookup, (tuple, list)):
                filters[field] = getattr(fields['fk'][lookup[0]], lookup[1])
            else:
                filters[field] = fields['simple'][lookup]
        try:
            return self.get(**filters)
        except self.model.DoesNotExist:
            return None

    def create_or_update_from_dict(self, data):
        """
        Taking a dict (passed in the data argument), try to update an existing
        object that match some fields, or create a new one.
        Return the object, or None if no object could be updated/created.
        """
        fields = self.get_object_fields_from_dict(data)

        if not fields:
            return None

        # get or create a new object
        obj = self.get_from_identifiers(fields)
        if not obj:
            obj = self.model(fetched_at=datetime.utcnow())

        # store siple filelds and FKs
        for field, value in fields['simple'].iteritems():
            setattr(obj, field, value)

        for field, value in fields['fk'].iteritems():
            setattr(obj, field, value)

        # we need to save the object before saving m2m
        obj.save()

        # finaaly save m2m
        for field, values in fields['many'].iteritems():
            field = getattr(obj, field)
            if hasattr(field, 'clear'):
                # if the other side is a non-nullable FK, we cannot clear, only
                # add items (consider that in this case, they could not be
                # deleted on the github side)
                field.clear()
            field.add(*values)

        return obj

    def get_object_fields_from_dict(self, data):
        """
        Taking a dict (passed in the data argument), return the fields to use
        to update or create an object. The returned dict contains 3 entries:
            - 'simple' to hold values for simple fields
            - 'fk' to hold values (real model instances) for foreign keys
            - 'many' to hold list of real model instances for many to many fields
              or for the related relation of a fk (issues of a repository...)
        Eeach of these entries is a dict with the model field names as key, and
        the values to save in the model as value.
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
                    fields['many'][field_name] = model.objects.create_or_update_from_list(value)
                else:
                    fields['many'][field_name] = []

            elif isinstance(field, models.ForeignKey):
                # we have an external object to create
                if value:
                    model = field.related.parent_model if direct else field.model
                    fields['fk'][field_name] = model.objects.create_or_update_from_dict(value)
                else:
                    fields['fk'][field_name] = None

            elif isinstance(field, models.DateTimeField):
                # we need to convert a datetimefield
                if value:
                    fields['simple'][field_name] = dateutil.parser.parse(value)
                else:
                    fields['simple'][field_name] = None

            else:
                # it's a simple field
                fields['simple'][field_name] = value

        return fields


class WithRepositoryManager(GithubObjectManager):
    """
    This manager si to be used for models based on GithubObject which have a
    repository field that is a FK toward the Repository model.
    The get_object_fields_from_dict is enhance to find the matching repository
    based on the url field from github in case of github don't tell us to which
    repository belongs the object.
    """

    def get_object_fields_from_dict(self, data):
        """
        In addition to the default get_object_fields_from_dict, try to guess the
        repository the objects belongs to, from the url found in the data given
        by the github api. Only set if the repository is found.
        """
        from .models import Repository

        fields = super(WithRepositoryManager, self).get_object_fields_from_dict(data)

        # add the repository if needed
        if 'repository' not in fields['fk']:
            repository = Repository.objects.get_by_url(data.get('url', None))
            if repository:
                fields['fk']['repository'] = repository

        return fields


class GithubUserManager(GithubObjectManager, UserManager):
    """
    This manager is for the GithubUser model, and is based on the default
    UserManager, and the GithubObjectManager to allow creation/update from data
    coming from the github api.
    The get_object_fields_from_dict is enhance to compute the is_orginization
    flag.
    """

    def get_object_fields_from_dict(self, data):
        """
        In addition to the default get_object_fields_from_dict, set the
        is_orginization flag based on the value of the User field given by the
        github api.
        """
        fields = super(GithubUserManager, self).get_object_fields_from_dict(data)

        # add the is_orginization field if needed
        if 'is_orginization' not in fields['simple']:
            fields['simple']['is_orginization'] = data.get('type', 'User') == 'Organization'

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
    """
    issue_finder = re.compile('^https?://api\.github\.com/repos/(?:[^/]+/[^/]+)/issues/(?P<number>\w+)(?:/|$)')

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


class IssueCommentManager(GithubObjectManager):
    """
    This manager is for the IssueComment model, with an enhanced
    get_object_fields_from_dict method, to get the issue and to compute the
    is_pull_request flag.
    flag.
    """

    def get_object_fields_from_dict(self, data):
        """
        In addition to the default get_object_fields_from_dict, try to guess the
        issue the comment belongs to, from the issue_url found in the data given
        by the github api. Only set if the issue is found.
        Also set the is_pull_request flag based on the 'diff_url' attribute of
        the 'pull_request' dict in the data given by the github api.
        """
        from .models import Issue

        fields = super(IssueCommentManager, self).get_object_fields_from_dict(data)

        # add the issue if needed
        if 'issue' not in fields['fk']:
            issue = Issue.objects.get_by_url(data.get('issue_url', None))
            if issue:
                fields['fk']['issue'] = issue

        # check if it's a pull request
        if 'is_pull_reques' not in fields['simple']:
            fields['simple']['is_pull_request'] = bool(data.get('pull_request', {}).get('diff_url', False))

        return fields
