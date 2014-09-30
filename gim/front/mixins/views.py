from copy import deepcopy
import json
from urlparse import parse_qs

from django.contrib import messages
from django.forms.forms import NON_FIELD_ERRORS
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.functional import cached_property

from gim.core.models import Repository, Issue
from gim.subscriptions.models import Subscription, SUBSCRIPTION_STATES


class WithAjaxRestrictionViewMixin(object):
    """
    If the "ajax_only" attribute is set to True, posting to the form will raise
    a "method not allowed" error to the user
    """
    ajax_only = False

    def dispatch(self, request, *args, **kwargs):
        if self.ajax_only and not request.is_ajax():
            return self.http_method_not_allowed(self.request)
        return super(WithAjaxRestrictionViewMixin, self).dispatch(request, *args, **kwargs)

    def render_messages(self, **kwargs):
        return render(self.request, 'front/messages.html', **kwargs)

    def render_form_errors_as_json(self, form, code=422):
        """
        To be used in form_invalid to return the errors in json format to be
        used by the js
        """
        json_data = json.dumps({
            'errors': form._errors
        })
        return HttpResponse(
            json_data,
            content_type='application/json',
            status=code,
        )

    def render_form_errors_as_messages(self, form, show_fields=True, **kwargs):
        """
        To be used in form_invalid to return nothing but messages (added to the
        content via a middleware)
        """
        for field, errors in form._errors.items():
            for error in errors:
                msg = error
                if show_fields and field != NON_FIELD_ERRORS:
                    msg = '%s: %s' % (field, error)
                messages.error(self.request, msg)
        return self.render_messages(**kwargs)


class LinkedToUserFormViewMixin(object):
    """
    A mixin for form views when the main object depends on a user, and
    using a form which is a subclass of LinkedToUserFormMixin, to have the
    current user passed to the form
    """
    def get_form_kwargs(self):
        kwargs = super(LinkedToUserFormViewMixin, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class WithQueryStringViewMixin(object):

    def get_qs_parts(self, context):
        """
        Get the querystring parts from the context
        """
        if 'querystring_parts' not in context:
            context['querystring_parts'] = {}
        return deepcopy(context['querystring_parts'])

    def get_context_data(self, **kwargs):
        """
        By default, simply split the querystring in parts for use in other
        views, and put the parts and the whole querystring in the context
        """
        context = super(WithQueryStringViewMixin, self).get_context_data(**kwargs)

        # put querystring parts in a dict
        qs = self.request.META.get('QUERY_STRING', '')
        qs_dict = parse_qs(qs)
        qs_parts = {}
        for key, values in qs_dict.items():
            if not len(values):
                continue
            if len(values) > 1:
                qs_parts[key] = values
            elif ',' in values[0]:
                qs_parts[key] = values[0].split(',')
            else:
                qs_parts[key] = values[0]

        context.update({
            'querystring_parts': qs_parts,
            'querystring': qs,
        })

        return context


class DependsOnSubscribedViewMixin(object):
    """
    A simple mixin with a "get_allowed_repositories" method which returns a
    queryset with allowed repositories for the user given the "allowed_rights"
    attribute of the class.
    Depends on nothing
    """
    allowed_rights = SUBSCRIPTION_STATES.READ_RIGHTS

    def get_allowed_repositories(self, rights=None):
        """
        Limit repositories to the ones subscribed by the user
        """
        if rights is None:
            rights = self.allowed_rights
        filters = {
            'subscriptions__user': self.request.user
        }
        if rights != SUBSCRIPTION_STATES.ALL_RIGHTS:
            filters['subscriptions__state__in'] = rights

        return Repository.objects.filter(**filters)


class WithSubscribedRepositoriesViewMixin(DependsOnSubscribedViewMixin):
    """
    A mixin that will put the list of all subscribed repositories in the context.
    Depends only on DependsOnSubscribedViewMixin to get the list of allowed
    repositories
    Provides also a list of all the subscriptions as a cached property
    """
    subscriptions_list_rights = SUBSCRIPTION_STATES.READ_RIGHTS

    @property
    def subscriptions(self):
        """
        Return (and cache) the list of all subscriptions of the current user
        based on the "subscriptions_list_rights" attribute
        """
        if not hasattr(self, '_subscriptions'):
            self._subscriptions = self.request.user.subscriptions.all()
            if self.subscriptions_list_rights != SUBSCRIPTION_STATES.ALL_RIGHTS:
                self._subscriptions = self._subscriptions.filter(
                                        state__in=self.subscriptions_list_rights)
        return self._subscriptions

    def get_context_data(self, **kwargs):
        """
        Add the list of subscribed repositories in the context, in a variable
        named "subscribed_repositories".
        """
        context = super(WithSubscribedRepositoriesViewMixin, self).get_context_data(**kwargs)

        context['subscribed_repositories'] = self.get_allowed_repositories(
                rights=self.subscriptions_list_rights
           ).extra(select={
                    'lower_name': 'lower(name)',
                    'lower_owner': 'lower(username)',
                }
            ).select_related('owner').order_by('lower_owner', 'lower_name')

        return context


class WithSubscribedRepositoryViewMixin(DependsOnSubscribedViewMixin):
    """
    A mixin that is meant to be used when a view depends on a repository.
    Provides
    - a "repository" property that'll get the repository depending on
    the ones allowed by the "allowed_rights" attribute provided by
    DependsOnSubscribedViewMixin, and the url params.
    - a "get_repository_filter_args" to use to filter a model on a repository's name
    and its owner's username
    And finally, put the repository and its related subscription in the context
    """
    def get_repository_filter_args(self, filter_root=''):
        """
        Return a dict with attribute to filter a model for a given repository's
        name and its owner's username as given in the url.
        Use the "filter_root" to prefix the filter.
        """
        if filter_root and not filter_root.endswith('__'):
            filter_root += '__'
        return {
            '%sowner__username' % filter_root: self.kwargs['owner_username'],
            '%sname' % filter_root: self.kwargs['repository_name'],
        }

    @property
    def repository(self):
        """
        Return (and cache) the repository. Raise a 404 if the current user is
        not allowed to use it, depending on the "allowed_rights" attribute
        """
        if not hasattr(self, '_repository'):

            qs = self.get_allowed_repositories()
            self._repository = get_object_or_404(qs.select_related('owner'),
                                                  **self.get_repository_filter_args())
        return self._repository

    @property
    def subscription(self):
        """
        Return (and cache) the subscription for the current user/repository
        """
        if not hasattr(self, '_subscription'):
            self._subscription = Subscription.objects.get(user=self.request.user,
                                                repository=self.repository)
        return self._subscription

    def get_context_data(self, **kwargs):
        """
        Put the current repository and its related subscription in the context
        """
        context = super(WithSubscribedRepositoryViewMixin, self).get_context_data(**kwargs)
        context['current_repository'] = self.repository
        context['current_subscription'] = self.subscription
        return context

    @cached_property
    def collaborators_ids(self):
        """
        Return the ids of all collaborators
        """
        return self.repository.collaborators.all().values_list('id', flat=True)


class SubscribedRepositoryViewMixin(WithSubscribedRepositoryViewMixin):
    """
    A simple mixin to use for views when the main object is a repository.
    Use the kwargs in the url to fetch it from database, using the
    "allowed_rights" attribute to limit to these rights for the current user.
    """
    model = Repository
    context_object_name = 'current_repository'

    def get_object(self, queryset=None):
        """
        Full overwrite of the method to return the repository got matching url
        params and the "allowed_rights" attribute for the current user
        """
        return self.repository


class DependsOnSubscribedRepositoryViewMixin(WithSubscribedRepositoryViewMixin):
    """
    A simple mixin to use for views when the main object depends on a repository
    Will limit entries to ones mathing the repository fetched using url params
    and the "allowed_rights" attribute.
    The "repository_related_name" attribute is the name to use to filter only
    on the current repository.
    """
    repository_related_name = 'repository'

    def get_queryset(self):
        """
        Return a queryset based on the current repository and allowed rights.
        """
        return self.model._default_manager.filter(**{
                self.repository_related_name: self.repository
            })


class LinkedToRepositoryFormViewMixin(WithAjaxRestrictionViewMixin, DependsOnSubscribedRepositoryViewMixin):
    """
    A mixin for form views when the main object depends on a repository, and
    using a form which is a subclass of LinkedToRepositoryFormMixin, to have the
    current repository passed to the form
    """
    def get_form_kwargs(self):
        kwargs = super(LinkedToRepositoryFormViewMixin, self).get_form_kwargs()
        kwargs['repository'] = self.repository
        return kwargs


class WithIssueViewMixin(WithSubscribedRepositoryViewMixin):
    """
    A mixin that is meant to be used when a view depends on a issue.
    Provides stuff provided by WithSubscribedRepositoryViewMixin, plus:
    - a "issue" property that'll get the issue depending on the repository and
    the "number" url params
    - a "get_issue_filter_args" to use to filter a model on a repository's name,
    its owner's username, and an issue number
    And finally, put the issue in the context
    """
    def get_issue_filter_args(self, filter_root=''):
        """
        Return a dict with attribute to filter a model for a given repository's
        name, its owner's username and an issue number as given in the url.
        Use the "filter_root" to prefix the filter.
        """
        if filter_root and not filter_root.endswith('__'):
            filter_root += '__'
        return {
            '%srepository_id' % filter_root: self.repository.id,
            '%snumber' % filter_root: self.kwargs['issue_number']
        }

    @property
    def issue(self):
        """
        Return (and cache) the issue. Raise a 404 if the current user is
        not allowed to use its repository, or if the issue is not found
        """
        if not hasattr(self, '_issue'):
            self._issue = get_object_or_404(
                            Issue.objects.select_related('repository__owner'),
                            **self.get_issue_filter_args())
        return self._issue

    def get_context_data(self, **kwargs):
        """
        Put the current issue in the context
        """
        context = super(WithIssueViewMixin, self).get_context_data(**kwargs)
        context['current_issue'] = self.issue
        return context


class DependsOnIssueViewMixin(WithIssueViewMixin, DependsOnSubscribedRepositoryViewMixin):
    """
    A simple mixin to use for views when the main object depends on a issue
    Will limit entries to ones mathing the issue fetched using url params
    and the "allowed_rights" attribute.
    The "issue_related_name" attribute is the name to use to filter only
    on the current issue.
    """
    issue_related_name = 'issue'
    repository_related_name = 'issue__repository'

    def get_queryset(self):
        """
        Return a queryset based on the current repository, issue, and allowed
        rights.
        """
        return self.model._default_manager.filter(**{
                self.issue_related_name: self.issue
            })


class LinkedToIssueFormViewMixin(WithAjaxRestrictionViewMixin, DependsOnIssueViewMixin):
    """
    A mixin for form views when the main object depends on an issue, and
    using a form which is a subclass of LinkedToIssueFormMixin, to have the
    current issue passed to the form
    """
    def get_form_kwargs(self):
        kwargs = super(LinkedToIssueFormViewMixin, self).get_form_kwargs()
        kwargs['issue'] = self.issue
        return kwargs


class LinkedToCommitFormViewMixin(WithAjaxRestrictionViewMixin):
    """
    A mixin for form views when the main object depends on a commit, and
    using a form which is a subclass of LinkedToCommitFormMixin, to have the
    current commit passed to the form
    """
    def get_form_kwargs(self):
        kwargs = super(LinkedToCommitFormViewMixin, self).get_form_kwargs()
        kwargs['commit'] = self.commit
        return kwargs


class DeferrableViewPart(object):
    deferred_template_name = 'front/base_deferred_block.html'
    auto_load = True

    @property
    def part_url(self):
        # must be defined in the final class
        raise NotImplementedError()

    def inherit_from_view(self, view):
        self.args = view.args
        self.kwargs = view.kwargs
        self.request = view.request

    def get_context_data(self, **kwargs):
        context = super(DeferrableViewPart, self).get_context_data(**kwargs)
        context.update({
            'defer_url': self.part_url,
        })
        return context

    def get_as_part(self, main_view, **kwargs):
        self.inherit_from_view(main_view)
        return self.render_part(**kwargs)

    def render_part(self, **kwargs):
        response = self.get(self.request, **kwargs)
        response.render()
        return response.content

    def get_deferred_context_data(self, **kwargs):
        kwargs.update({
            'view': self,
            'deferred': True,
            'defer_url': self.part_url,
            'auto_load': self.auto_load,
        })
        return kwargs

    def get_deferred_template_names(self):
        return [self.deferred_template_name]

    def get_as_deferred(self, main_view, **kwargs):
        self.inherit_from_view(main_view)
        return self.render_deferred(**kwargs)

    def render_deferred(self, **kwargs):
        response = self.response_class(
            request = self.request,
            template = self.get_deferred_template_names(),
            context = self.get_deferred_context_data(**kwargs),
            content_type = self.content_type,
        )
        response.render()
        return response.content
