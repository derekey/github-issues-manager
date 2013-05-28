from copy import deepcopy
from urlparse import parse_qs

from django.views.generic import DetailView


class BaseFrontView(DetailView):

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
        context = super(BaseFrontView, self).get_context_data(**kwargs)
        
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
