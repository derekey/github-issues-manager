from django.views.generic import DetailView
from django.shortcuts import get_object_or_404

from core.models import Repository


class BaseRepositoryView(DetailView):
    model = Repository
    template_name = 'front/sample.html'
    context_object_name = 'repository'

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()

        owner_username = self.kwargs['owner_username']
        repository_name = self.kwargs['repository_name']

        filters = {
            'owner__username': owner_username,
            'name': repository_name
        }

        repository = get_object_or_404(queryset, **filters)

        return repository
