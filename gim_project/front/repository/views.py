from django.shortcuts import get_object_or_404
from django.core.urlresolvers import reverse_lazy
from django.utils.decorators import classonlymethod
from django.views.generic import DetailView

from ..views import SubscribedRepositoriesMixin
from subscriptions.models import SUBSCRIPTION_STATES
from core.models import Repository


class RepositoryMixin(SubscribedRepositoriesMixin, DetailView):
    context_object_name = 'current_repository'

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

        self.repository = get_object_or_404(queryset.select_related('owner'), **filters)

        return self.repository


class BaseRepositoryView(RepositoryMixin):
    # details vue attributes
    template_name = 'front/repository/base.html'

    # specific attributes to define in subclasses
    name = None
    url_name = None
    default_qs = None

    # set to False to not display in the main menu bar
    display_in_menu = True

    # internal attributes
    main_views = []

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

        # we need a list of all main views for this repository
        repo_main_views = []
        reverse_kwargs = self.repository.get_reverse_kwargs()
        for view_class in BaseRepositoryView.main_views:
            main_view = {
                'url_name': view_class.url_name,
                'display_in_menu': view_class.display_in_menu,
                'url': reverse_lazy('front:repository:%s' % view_class.url_name, kwargs=reverse_kwargs),
                'qs': view_class.default_qs,
                'is_current': self.main_url_name == view_class.url_name,
                'title': view_class.name
            }
            repo_main_views.append(main_view)

        context['repository_main_views'] = repo_main_views

        return context


class LinkedToRepositoryFormView(object):
    repository_related_name = 'repository'
    allowed_rights = (SUBSCRIPTION_STATES.USER, SUBSCRIPTION_STATES.ADMIN)

    def get_repository_kwargs(self):
        return {
            'owner__username': self.kwargs.get('owner_username', None),
            'name': self.kwargs.get('repository_name', None),
        }

    def get_queryset(self):
        repository_kwargs = self.get_repository_kwargs()

        self.repository = get_object_or_404(
            Repository.objects.filter(
                    subscriptions__user=self.request.user,
                    subscriptions__state__in=self.allowed_rights,
                ),
            **repository_kwargs)

        return self.model._default_manager.filter(**{
                self.repository_related_name: self.repository
            })
