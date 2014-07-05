__all__ = [
    'GITHUB_STATUS_CHOICES',
]

from datetime import datetime, timedelta
from itertools import product
from math import ceil
from urlparse import urlsplit, parse_qs

from django.db import models, DatabaseError

from extended_choices import Choices

from ..ghpool import (
    ApiError,
    ApiNotFoundError,
    parse_header_links,
    prepare_fetch_headers,
)
from ..managers import MODE_ALL, GithubObjectManager


class MinDateRaised(Exception):
    pass


GITHUB_STATUS_CHOICES = Choices(
    ('WAITING_CREATE', 1, u'Awaiting creation'),
    ('WAITING_UPDATE', 2, u'Awaiting update'),
    ('WAITING_DELETE', 3, u'Awaiting deletion'),
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

GITHUB_STATUS_CHOICES.NOT_READY = (
    GITHUB_STATUS_CHOICES.WAITING_DELETE,
    GITHUB_STATUS_CHOICES.WAITING_CREATE,
    GITHUB_STATUS_CHOICES.ERROR_CREATE
)


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
    github_per_page = {'min': 10, 'max': 100}
    github_date_field = None  # ex ('updated_at', 'updated',   'desc')
                              #      obj field     sort param  direction param
    github_reverse_order = False  # if entries are given by github in forced reverse order
                                  # See CommitComment

    delete_missing_after_fetch = True

    class Meta:
        abstract = True
        app_label = 'core'

    def __str__(self):
        return unicode(self).encode('utf-8')

    def fetch(self, gh, defaults=None, force_fetch=False, parameters=None,
                                                        meta_base_name=None):
        """
        Fetch data from github for the current object and update itself.
        If defined, "defaults" is a dict with values that will be used if not
        found in fetched data.
        The meta_base_name argument is used to get the identifiers to use for
        calling the github api, and the 'fetched_at' field to use for the
        'If-Modified-Since' header and field to updated.
        """
        if meta_base_name:
            identifiers = getattr(self, 'github_callable_identifiers_for_%s' % meta_base_name)
            fetched_at_field = '%s_fetched_at' % meta_base_name
        else:
            identifiers = self.github_callable_identifiers
            fetched_at_field = 'fetched_at'

        request_headers = prepare_fetch_headers(
                    if_modified_since=None if force_fetch else getattr(self, fetched_at_field),
                    github_format=self.github_format)
        response_headers = {}

        try:
            obj = self.__class__.objects.get_from_github(
                gh=gh,
                identifiers=identifiers,
                modes=MODE_ALL,
                defaults=defaults,
                parameters=parameters,
                request_headers=request_headers,
                response_headers=response_headers,
                fetched_at_field=fetched_at_field,
                force_update=force_fetch,
            )

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
                    parameters=None, remove_missing=True, force_fetch=False,
                    meta_base_name=None, modes=MODE_ALL, max_pages=None,
                    filter_queryset=None):
        """
        Fetch data from github for the given m2m or related field.
        If defined, "vary" is a dict of list of parameters to fetch. For each
        key of this dict, all values of the list will be used as a parameter,
        one after the other. If many keys are in "vary", all combinations will
        be fetched.
        If defined, "defaults" is a dict with values that will be used if not
        found in fetched data.
        By default, the field_name is not only used to know which list to update,
        but also as a base used to know which "metadata" fields to use/update
        (fetched_at, etag, github_callable_identifiers_for_). To use another
        base, simply pass it to the `meta_base_name` argument.
        Mode must be a tuple containing none, one or both of "create" and
        "update". If None is passed, the default is both values.
        """
        field, _, direct, m2m = self._meta.get_field_by_name(field_name)
        if direct:
            # we are on a field of the current model, the objects to create or
            # update are on the model on the other side of the relation
            model = field.related.parent_model
        else:
            # the field is originally defined on the other side of the relation,
            # we have a RelatedObject with the model on the other side of the
            # relation to use to create or update are on the current model
            model = field.model

        if not meta_base_name:
            meta_base_name = field_name

        if modes is None:
            modes = MODE_ALL

        if parameters is None:
            parameters = {}

        identifiers = getattr(self, 'github_callable_identifiers_for_%s' % meta_base_name)

        per_page_parameter = {
            'per_page': parameters.get('per_page', model.github_per_page['max'])
        }

        # prepare headers to add in the request
        min_date = None
        if_modified_since = None
        fetched_at_field = '%s_fetched_at' % meta_base_name
        last_page_field = '%s_last_page' % meta_base_name

        if not force_fetch:
            if hasattr(self, fetched_at_field):
                # if we have a fetch date, use it
                fetched_at = getattr(self, fetched_at_field)
                if fetched_at:
                    # tell github we have all data since this date
                    if_modified_since = fetched_at
                    # limit to a few items per list when updating a repository
                    # only if per_page not forced and last fetch is recent
                    if (not parameters.get('per_page')
                        and not model.github_reverse_order
                        and datetime.utcnow() - fetched_at < timedelta(days=1)):
                        per_page_parameter['per_page'] = model.github_per_page['min']

                    # do we have to check for a min date ?
                    if model.github_date_field:
                        date_field_name, sort, direction = model.github_date_field
                        # sort_param = (parameters or {}).get('sort')
                        # direction_param = (parameters or {}).get('direction')
                        # if (not sort and not sort_param or sort and sort_param == sort)\
                        #     and (not direction and not direction_param or direction and direction_param == direction):
                        if parameters.get('sort') == sort and\
                           parameters.get('direction') == direction:
                            min_date = fetched_at

        request_headers = prepare_fetch_headers(
                    if_modified_since=if_modified_since,
                    github_format=model.github_format)

        def fetch_page_and_next(objs, parameters, min_date):
            """
            Fetch a page of objects with the given parameters, and if github
            tell us there is a "next" page, tell caller to continue fetching by
            returning the parameters for the next page as first return argument
            (or None if no next page).
            Return the etag header of the page as second argument

            """
            response_headers = {}
            etag = None
            last_page_ok = None

            page_objs = []

            try:
                page_objs = model.objects.get_from_github(
                    gh=gh,
                    identifiers=identifiers,
                    modes=modes,
                    defaults=defaults,
                    parameters=parameters,
                    request_headers=request_headers,
                    response_headers=response_headers,
                    min_date=min_date,
                    force_update=force_fetch,
                )

            except ApiNotFoundError:
                # no data for this list (issues may be no activated, for example)
                last_page_ok = int(parameters.get('page', 1)) - 1
            except ApiError, e:
                if e.response and e.response['code'] in (410, ):
                    # no data for this list (issues may be no activated, for example)
                    last_page_ok = int(parameters.get('page', 1)) - 1
                else:
                    raise
            except Exception:
                raise
            else:
                last_page_ok = int(parameters.get('page', 1))

            etag = response_headers.get('etag') or None

            if not page_objs:
                # no fetched objects, we're done
                last_page_ok -= 1
                return None, etag, last_page_ok

            objs += page_objs

            # if we reached the min_date, stop
            if min_date and not model.github_reverse_order:
                obj_min_date = getattr(page_objs[-1], model.github_date_field[0])
                if obj_min_date and obj_min_date < min_date:
                    raise MinDateRaised(etag)

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
                    # params for next page
                    return next_page_parameters, etag, last_page_ok

            # manage model without pagination activated on the github side
            # but only if we receivend enough data to let us think we may have
            # more than one page
            elif len(objs) >= parameters.get('per_page'):  # == should suffice but...
                # simply increment the page number
                next_page_parameters = parameters.copy()
                next_page_parameters['page'] = int(parameters.get('page', 1)) + 1
                # params for next page
                return next_page_parameters, etag, last_page_ok

            # no more page, stop
            return None, etag, last_page_ok

        if not vary:
            # no varying parameter, fetch with an empty set of parameters, with
            # a simple etag field
            parameters_combinations = [({}, '%s_etag' % meta_base_name)]
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
                etag_field = '%s_%s_etag' % (meta_base_name, etag_varation)
                parameters_combinations.append((dikt, etag_field))

        # add per_page option
        for parameters_combination, _ in parameters_combinations:
            parameters_combination.update(per_page_parameter)
            if parameters:
                parameters_combination.update(parameters)

        # fetch data for each combination of varying parameters
        etags = {}
        objs = []
        cache_hit = False
        max_pages_raised = False
        something_fetched = False
        last_page_ok = None

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
                page = int(parameters.get('page', 0))
                pages_total = 0
                page_parameters = parameters_combination.copy()
                while True:
                    page += 1
                    page_parameters, page_etag, last_page_ok = \
                        fetch_page_and_next(objs, page_parameters, min_date)
                    pages_total += 1
                    if page == 1 or model.github_reverse_order:
                        etags[etag_field] = page_etag
                        if request_etag:
                            # clear if-none-match header for pages > 1
                            request_headers = prepare_fetch_headers(
                                if_modified_since=if_modified_since,
                                if_none_match=None,
                                github_format=model.github_format)

                    if page_parameters is None:
                        break

                    if max_pages and pages_total >= max_pages:
                        max_pages_raised = True
                        break

            except MinDateRaised, e:
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
            # but only if we had all fresh data !
            started_at_first_page = int(parameters.get('page', 1)) in (0, 1, None)
            do_remove = (remove_missing
                     and not cache_hit
                     and modes == MODE_ALL
                     and not max_pages_raised
                     and started_at_first_page
                )
            save_etags_and_fetched_at = started_at_first_page
            self.update_related_field(field_name,
                                      [obj.id for obj in objs],
                                      do_remove=do_remove,
                                      save_etags_and_fetched_at=save_etags_and_fetched_at,
                                      etags=etags,
                                      fetched_at_field=fetched_at_field,
                                      filter_queryset=filter_queryset,
                                      last_page_field=last_page_field,
                                      last_page=last_page_ok)

        # we return the number of fetched objects
        if not objs:
            return 0
        else:
            return len(objs)

    def update_related_field(self, field_name, ids, do_remove=True,
                                save_etags_and_fetched_at=True, etags=None,
                                fetched_at_field=None, filter_queryset=None,
                                last_page_field=None, last_page=None):
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
        existing_queryset = instance_field
        if filter_queryset:
            existing_queryset = instance_field.filter(filter_queryset)
        existing_ids = set(existing_queryset.order_by().values_list('id', flat=True))
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
                try:
                    instance_field.remove(*to_remove)
                except DatabaseError, e:
                    # sqlite limits the vars passed in a request to 999
                    # In this case, we loop on the data by slice of 950 obj to remove
                    if u'%s' % e != 'too many SQL variables':
                        raise
                    per_iteration = 950  # do not use 999 has we may have other vars for internal django filter
                    to_remove = list(to_remove)
                    iterations = int(ceil(len(to_remove) / float(per_iteration)))
                    for iteration in range(0, iterations):
                        instance_field.remove(*to_remove[iteration * per_iteration:(iteration + 1) * per_iteration])
            else:
                # The relation cannot be removed, because the current object is
                # a non-nullable fk of the other objects. In this case we are
                # sure the object is fully deleted on the github side, or
                # attached to another object, but we don't care here, so we
                # delete the objects.
                # Example: a milestone of a repository is not fetched via
                # fetch_milestones? => we know it's deleted
                # We also manage here relations via through tables
                if hasattr(instance_field, 'through'):
                    model = instance_field.through
                    filter = {
                        '%s__id' % instance_field.source_field_name: self.id,
                        '%s__id__in' % instance_field.target_field_name: to_remove,
                    }
                else:
                    model = instance_field.model
                    filter = {'id__in': to_remove}

                to_delete_queryset = model.objects.filter(**filter)
                if filter_queryset:
                    to_delete_queryset = to_delete_queryset.filter(filter_queryset)
                model.objects.delete_missing_after_fetch(to_delete_queryset)

        # if we have new relations, add them
        to_add = fetched_ids - existing_ids
        if to_add:
            count['added'] = len(to_add)
            if hasattr(instance_field, 'add'):
                try:
                    instance_field.add(*to_add)
                except DatabaseError, e:
                    # sqlite limits the vars passed in a request to 999
                    # In this case, we loop on the data by slice of 950 obj to add
                    if u'%s' % e != 'too many SQL variables':
                        raise
                    per_iteration = 950  # do not use 999 has we may have other vars for internal django filter
                    to_add = list(to_add)
                    iterations = int(ceil(count['added'] / float(per_iteration)))
                    for iteration in range(0, iterations):
                        instance_field.add(*to_add[iteration * per_iteration:(iteration + 1) * per_iteration])

            elif hasattr(instance_field, 'through'):
                model = instance_field.through
                objs = [
                    model(**{
                        '%s_id' % instance_field.source_field_name: self.id,
                        '%s_id' % instance_field.target_field_name: obj_id
                    })
                    for obj_id in to_add
                ]
                model.objects.bulk_create(objs)  # size limit for sqlite managed by django

        # check if we have something to save on the main object
        update_fields = []

        if save_etags_and_fetched_at:
            all_field_names = self._meta.get_all_field_names()
            # can we save a fetch date ?
            if not fetched_at_field:
                fetched_at_field = '%s_fetched_at' % field_name
            setattr(self, fetched_at_field, datetime.utcnow())
            if fetched_at_field in all_field_names:
                update_fields.append(fetched_at_field)

            # do we have etags to save ?
            if etags:
                for etag_field, etag in etags.items():
                    setattr(self, etag_field, etag)
                    if etag_field in all_field_names:
                        update_fields.append(etag_field)

        if last_page_field and hasattr(self, last_page_field) and last_page is not None:
            setattr(self, last_page_field, last_page)
            update_fields.append(last_page_field)

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

    def dist_edit(self, gh, mode, fields=None, values=None):
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
            if isinstance(field_name, tuple):
                key, field_name = field_name
            else:
                key = field_name

            if values and key in values:
                data[key] = values[key]
            else:
                if '__' in field_name:
                    field_name, subfield_name = field_name.split('__')
                    field, _, direct, is_m2m = self._meta.get_field_by_name(field_name)
                    relation = getattr(self, field_name)
                    if is_m2m or not direct:
                        # we have a many to many relationship
                        data[key] = list(relation.order_by().values_list(subfield_name, flat=True))
                    else:
                        # we have a foreignkey
                        data[key] = None if not relation else getattr(relation, subfield_name)
                else:
                    # it's a direct field
                    data[key] = getattr(self, field_name)
                    if isinstance(data[field_name], datetime):
                        data[key] = data[field_name].isoformat()

        # prepare the request
        identifiers = self.github_callable_identifiers if mode == 'update' else self.github_callable_create_identifiers
        gh_callable = self.__class__.objects.get_github_callable(gh, identifiers)
        method = getattr(gh_callable, 'patch' if mode == 'update' else 'post')
        request_headers = prepare_fetch_headers(github_format=self.github_format)

        # make the request and get fresh data for the object
        result = method(request_headers=request_headers, **data)

        # get defaults to update the data with fresh data we just got
        defaults = self.defaults_create_values()

        # if we are in create mode, we delete the object to recreate it with
        # the data we just got
        if mode == 'create':
            self.delete()

        # update the object on our side
        return self.__class__.objects.create_or_update_from_dict(
                                                            data=result,
                                                            defaults=defaults,
                                                            force_update=True)


class GithubObjectWithId(GithubObject):
    github_id = models.PositiveIntegerField(unique=True, null=True, blank=True)

    github_matching = dict(GithubObject.github_matching)
    github_matching.update({
        'id': 'github_id'
    })
    github_ignore = GithubObject.github_ignore + ('github_id', )
    github_identifiers = {'github_id': 'github_id'}

    class Meta:
        abstract = True
        app_label = 'core'
