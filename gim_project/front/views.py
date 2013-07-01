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

    @property
    def subscriptions(self):
        if not hasattr(self, '_subscriptions'):
            self._subscriptions = list(self.request.user.subscriptions.exclude(
                                            state=SUBSCRIPTION_STATES.NORIGHTS))
        return self._subscriptions

    def get_queryset(self):
        """
        Limit repositories to the ones subscribed by the user
        """
        queryset = super(SubscribedRepositoriesMixin, self).get_queryset()
        repo_ids = [s.id for s in self.subscriptions]
        return queryset.filter(id__in=repo_ids)

    def get_context_data(self, **kwargs):
        """
        Add the list of subscribed repositories in the context, in a variable
        named "subscribed_repositories". The list is not lazy !
        """
        context = super(SubscribedRepositoriesMixin, self).get_context_data(**kwargs)

        context['subscribed_repositories'] = list(
                            self.get_queryset().all().select_related('owner'))

        return context
