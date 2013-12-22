from django.views.generic import FormView, TemplateView, RedirectView
from django.shortcuts import redirect
from django.contrib import messages
from django.core.urlresolvers import reverse_lazy

from core.models import Repository, GithubUser
from subscriptions.models import (WaitingSubscription,
                                  WAITING_SUBSCRIPTION_STATES,
                                  SUBSCRIPTION_STATES, )

from core.tasks.repository import FirstFetch

from ...views import BaseFrontViewMixin
from .forms import AddRepositoryForm, RemoveRepositoryForm


class ToggleRepositoryBaseView(BaseFrontViewMixin, FormView):
    """
    Base view to use to add/remove a repository
    """

    success_url = reverse_lazy('front:dashboard:repositories:choose')
    http_method_names = [u'post']

    def get_form_kwargs(self):
        """
        Add the current request's user in the kwargs to use in the form
        """
        kwargs = super(ToggleRepositoryBaseView, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_invalid(self, form):
        """
        If the form is invalid, return to the list of repositories the user
        can add, with an error message
        """
        messages.error(self.request, form.get_main_error_message())
        return redirect(self.get_success_url())


class AddRepositoryView(ToggleRepositoryBaseView):
    form_class = AddRepositoryForm

    def form_valid(self, form):
        name = form.cleaned_data['name']

        # create the waiting subscription if not exists
        subscription, created = WaitingSubscription.objects.get_or_create(
            user=self.request.user,
            repository_name=name
        )

        if not created:
            # the subscription already exists, force the state and updated_at
            subscription.state = WAITING_SUBSCRIPTION_STATES.WAITING
            subscription.save()

        message = 'Your subscription to <strong>%s</strong> will be added shortly'
        # if the repository exists (and fetched), convert into a real subscription
        try:
            repository = subscription.repository
        except Repository.DoesNotExist:
            # add a job to fetch the repository
            FirstFetch.add_job(name, gh=self.request.user.get_connection())
        else:
            if repository.fetched_at:
                message = 'Your subscription to <strong>%s</strong> was just added'
                subscription.convert(form.can_use)

        messages.success(self.request, message % name)

        return super(AddRepositoryView, self).form_valid(form)


class RemoveRepositoryView(ToggleRepositoryBaseView):
    form_class = RemoveRepositoryForm

    def form_valid(self, form):
        name = form.cleaned_data['name']

        form.subscription.delete()

        messages.success(self.request, 'Your subscription to <strong>%s</strong> was just removed' % name)

        return super(RemoveRepositoryView, self).form_valid(form)


class ChooseRepositoryView(TemplateView):
    template_name = 'front/dashboard/repositories/choose.html'
    url_name = 'front:dashboard:repositories:choose'

    def get_waiting_subscriptions(self):
        """
        Return a dict of waiting subscriptions, with the repositories names as keys
        """
        return dict((s.repository_name, s) for s in self.request.user.waiting_subscriptions.all())

    def get_subscriptions(self):
        """
        Return a dict of subscriptions, with the repositories names as keys
        """
        return dict((s.repository.full_name, s) for s in self.request.user.subscriptions.all().select_related('repository__owner'))

    def get_avatar_url(self, username):
        if not hasattr(self, '_avatar_urls'):
            self._avatar_urls = {}
        if username not in self._avatar_urls:
            try:
                self._avatar_urls[username] = GithubUser.objects.get(
                                                username=username).avatar_url
            except GithubUser.DoesNotExist:
                self._avatar_urls[username] = None

        return self._avatar_urls[username]

    def get_context_data(self, *args, **kwargs):
        context = super(ChooseRepositoryView, self).get_context_data(*args, **kwargs)

        organizations_by_name = dict((org.username, org) for org in self.request.user.organizations.all())

        available_repos = set()
        for org in self.request.user.available_repositories or []:
            available_repos.update(['%s/%s' % (rep['owner'], rep['name']) for rep in org['repos']])

        waiting_subscriptions = self.get_waiting_subscriptions()
        subscriptions = self.get_subscriptions()

        # manage repositories that are not in user.available_repositories
        others_repos = {
            'name': '__others__',
            'repos': [],
        }
        for repo_name, subscription in waiting_subscriptions.iteritems():
            if repo_name not in available_repos:
                owner, name = subscription.repository_name.split('/')
                others_repos['repos'].append({
                    'no_infos': True,
                    'owner': owner,
                    'avatar_url': self.get_avatar_url(owner),
                    'name': name,
                })
        for repo_name, subscription in subscriptions.iteritems():
            if repo_name not in available_repos:
                others_repos['repos'].append({
                    'owner': subscription.repository.owner.username,
                    'avatar_url': subscription.repository.owner.avatar_url,
                    'name': subscription.repository.name,
                    'private': subscription.repository.private,
                    'is_fork': subscription.repository.is_fork,
                    'has_issues': subscription.repository.has_issues,
                    'rights': 'admin' if subscription.state == SUBSCRIPTION_STATES.ADMIN
                                      else 'push' if subscription.state == SUBSCRIPTION_STATES.USER
                                      else 'read'
                })

        context.update({
            'available_repositories': self.request.user.available_repositories + [others_repos],
            'waiting_subscriptions': waiting_subscriptions,
            'subscriptions': subscriptions,
            'organizations_by_name': organizations_by_name,
        })
        return context


class AskFetchAvailableRepositories(BaseFrontViewMixin, RedirectView):
    """
    Fetch the available repositories of the current user from github then
    redirect him to the subscriptions page
    """
    permanent = False
    http_method_names = [u'post']
    url = reverse_lazy("front:dashboard:repositories:choose")

    def post(self, *args, **kwargs):
        self.request.user.fetch_available_repositories()
        messages.success(self.request, 'The list of repositories you can subscribe to was just updated')
        return super(AskFetchAvailableRepositories, self).post(*args, **kwargs)
