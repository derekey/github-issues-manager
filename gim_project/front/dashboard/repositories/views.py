from itertools import chain

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
    ajax_success_url = reverse_lazy('front:dashboard:repositories:ajax-repo')
    http_method_names = [u'post']

    def __init__(self, *args, **kwargs):
        self.repo_full_name = None
        super(ToggleRepositoryBaseView, self).__init__(*args, **kwargs)

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
        self.repo_full_name = form.repo_full_name
        messages.error(self.request, form.get_main_error_message())
        return redirect(self.get_success_url())

    def get_success_url(self):
        """
        IF we are in ajax mode, redirect to the ajax view of the current repo
        """
        if self.request.is_ajax() and self.repo_full_name:
            return reverse_lazy('front:dashboard:repositories:ajax-repo',
                                kwargs={'name': self.repo_full_name})

        return super(ToggleRepositoryBaseView, self).get_success_url()


class AddRepositoryView(ToggleRepositoryBaseView):
    form_class = AddRepositoryForm

    def form_valid(self, form):
        name = self.repo_full_name = form.cleaned_data['name']

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
        name = self.repo_full_name = form.cleaned_data['name']

        form.subscription.delete()

        messages.success(self.request, 'Your subscription to <strong>%s</strong> was just removed' % name)

        return super(RemoveRepositoryView, self).form_valid(form)


class WithRepoDictMixin(object):

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

    def subscription_to_dict(self, subscription):
        return {
            'owner': subscription.repository.owner.username,
            'avatar_url': subscription.repository.owner.avatar_url,
            'name': subscription.repository.name,
            'private': subscription.repository.private,
            'is_fork': subscription.repository.is_fork,
            'has_issues': subscription.repository.has_issues,
            'rights': 'admin' if subscription.state == SUBSCRIPTION_STATES.ADMIN
                              else 'push' if subscription.state == SUBSCRIPTION_STATES.USER
                              else 'read'

        }

    def waiting_subscription_to_dict(self, subscription):
        owner, name = subscription.repository_name.split('/')
        return {
            'no_infos': True,
            'owner': owner,
            'avatar_url': self.get_avatar_url(owner),
            'name': name,
        }


class ShowRepositoryAjaxView(WithRepoDictMixin, TemplateView):
    template_name = 'front/dashboard/repositories/ajax_repo.html'

    def get_context_data(self, *args, **kwargs):
        context = super(ShowRepositoryAjaxView, self).get_context_data(*args, **kwargs)

        user = self.request.user

        full_name = self.kwargs['name']
        owner_name, repo_name = full_name.split('/')

        subscriptions = {}
        try:
            subscriptions[full_name] = user.subscriptions.filter(
                                    repository__owner__username=owner_name,
                                    repository__name=repo_name
                                ).select_related('repository_owner')[0]
        except IndexError:
            pass

        waiting_subscriptions = {}
        try:
            waiting_subscriptions[full_name] = user.waiting_subscriptions.filter(
                                                    repository_name=full_name)[0]
        except IndexError:
            pass

        # in available repositories ?
        try:
            repo = [r for r in list(chain(*[o['repos']
                                        for o in user.available_repositories]))
                   if r['owner'] == owner_name and r['name'] == repo_name][0]
        except IndexError:
            # in waiting subscriptions ?
            if full_name in waiting_subscriptions:
                repo = self.waiting_subscription_to_dict(waiting_subscriptions[full_name])

            # in real subscriptions ?
            elif full_name in subscriptions:
                repo = self.subscription_to_dict(subscriptions[full_name])

            # no repo anymore: it was a repo not in available ones that was justunsubscribed
            else:
                repo = None

        context.update({
            'repo': repo,
            'subscriptions': subscriptions,
            'waiting_subscriptions': waiting_subscriptions,
        })

        return context


class ChooseRepositoryView(WithRepoDictMixin, TemplateView):
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
                others_repos['repos'].append(self.waiting_subscription_to_dict(subscription))
        for repo_name, subscription in subscriptions.iteritems():
            if repo_name not in available_repos:
                others_repos['repos'].append(self.subscription_to_dict(subscription))

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
