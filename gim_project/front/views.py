from copy import deepcopy
from urlparse import parse_qs

from core.models import Repository
from subscriptions.models import SUBSCRIPTION_STATES


class BaseFrontViewMixin(object):

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
        context = super(BaseFrontViewMixin, self).get_context_data(**kwargs)

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


class SubscribedRepositoriesMixin(BaseFrontViewMixin):
    """
    Mixin to use when needing to list the subscribed repositories.
    Provide the model to use, the get_queryset method, and add
    'subscribed_repositories' in the context
    """
    model = Repository
    allowed_rights = SUBSCRIPTION_STATES.READ_RIGHTS

    @property
    def subscriptions(self):
        if not hasattr(self, '_subscriptions'):
            self._subscriptions = self.request.user.subscriptions.all()
            if self.allowed_rights != SUBSCRIPTION_STATES.ALL_RIGHTS:
                self._subscriptions = self._subscriptions.filter(
                                                state__in=self.allowed_rights)
        return self._subscriptions

    def get_queryset(self):
        """
        Limit repositories to the ones subscribed by the user
        """
        filters = {
            'subscriptions__user': self.request.user
        }
        if self.allowed_rights != SUBSCRIPTION_STATES.ALL_RIGHTS:
            filters['subscriptions__state__in'] = self.allowed_rights

        return Repository.objects.filter(**filters)

    def get_context_data(self, **kwargs):
        """
        Add the list of subscribed repositories in the context, in a variable
        named "subscribed_repositories".
        """
        context = super(SubscribedRepositoriesMixin, self).get_context_data(**kwargs)

        context['subscribed_repositories'] = Repository.objects.filter(
               subscriptions__user=self.request.user,
               subscriptions__state__in=SUBSCRIPTION_STATES.READ_RIGHTS,
           ).extra(select={
                    'lower_name': 'lower(name)',
                    'lower_owner': 'lower(username)',
                }
            ).select_related('owner').order_by('lower_owner', 'lower_name')

        return context


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
        response = self.get(self.request, **kwargs)
        response.render()
        return response.content

    def get_deferred_context_data(self, **kwargs):
        kwargs.update({
            'view': self,
            'defer_url': self.part_url,
            'auto_load': self.auto_load,
        })
        return kwargs

    def get_deferred_template_names(self):
        return [self.deferred_template_name]

    def get_as_deferred(self, main_view, **kwargs):
        self.inherit_from_view(main_view)
        response = self.response_class(
            request = self.request,
            template = self.get_deferred_template_names(),
            context = self.get_deferred_context_data(**kwargs),
            content_type = self.content_type,
        )
        response.render()
        return response.content
