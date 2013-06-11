from django.shortcuts import get_object_or_404
from django.core.urlresolvers import reverse_lazy
from django.utils.decorators import classonlymethod

from ..views import BaseFrontView
from core.models import Repository
from subscriptions.models import SUBSCRIPTION_STATES


class BaseRepositoryView(BaseFrontView):
    # details vue attributes
    model = Repository
    template_name = 'front/repository/base.html'
    context_object_name = 'current_repository'

    # specific attributes to define in subclasses
    name = None
    url_name = None
    default_qs = None

    # internal attributes
    main_views = []

    def get_queryset(self):
        """
        Limit repositories to the ones subscribed by the user
        """
        queryset = super(BaseRepositoryView, self).get_queryset()
        repo_ids = self.request.user.subscriptions.exclude(
            state=SUBSCRIPTION_STATES.NORIGHTS).values_list('repository_id', flat=True)
        return queryset.filter(id__in=repo_ids)

    def get_object(self, queryset=None):
        """
        Totally override this method to return a repository based on its
        owner's username and its name.
        """
        if queryset is None:
            queryset = self.get_queryset()

        owner_username = self.kwargs['owner_username']
        repository_name = self.kwargs['repository_name']

        filters = {
            'owner__username': owner_username,
            'name': repository_name
        }

        repository = get_object_or_404(queryset.select_related('owner'), **filters)

        return repository

    @classonlymethod
    def as_view(cls, *args, **kwargs):
        """
        Override to call register_main_view if the view is a main one
        """
        if BaseRepositoryView in cls.__bases__:
            BaseRepositoryView.register_main_view(cls)
        return super(BaseRepositoryView, cls).as_view(*args, **kwargs)

    @classonlymethod
    def register_main_view(cls, view_class):
        """
        Store views to display as main views
        """
        if view_class not in BaseRepositoryView.main_views:
            view_class.main_url_name = view_class.url_name
            BaseRepositoryView.main_views.append(view_class)

    def get_context_data(self, **kwargs):
        """
        Set default content for the repository views:
            - list of available repositories
            - list of all main views for this repository
        """
        context = super(BaseRepositoryView, self).get_context_data(**kwargs)

        # quick access to repository
        repository = context['current_repository']

        # we need a list of availables repositories
        all_repositories = self.get_queryset().all().select_related('owner')

        # we also need a list of all main views for this repository
        repo_main_views = []
        reverse_kwargs = repository.get_reverse_kwargs()
        for view_class in BaseRepositoryView.main_views:
            main_view = {
                'url': reverse_lazy('front:repository:%s' % view_class.url_name, kwargs=reverse_kwargs),
                'qs': view_class.default_qs,
                'is_current': self.main_url_name == view_class.url_name,
                'title': view_class.name
            }
            repo_main_views.append(main_view)

        context.update({
            'all_repositories': all_repositories,
            'repository_main_views': repo_main_views,
        })

        return context
