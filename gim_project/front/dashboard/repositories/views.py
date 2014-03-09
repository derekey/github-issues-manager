from collections import namedtuple
from itertools import groupby

from django.views.generic import FormView, TemplateView, RedirectView
from django.shortcuts import redirect
from django.contrib import messages
from django.core.urlresolvers import reverse_lazy

from limpyd_jobs import STATUSES

from core.models import (Repository, GithubUser, AVAILABLE_PERMISSIONS)
from subscriptions.models import (WaitingSubscription,
                                  WAITING_SUBSCRIPTION_STATES,
                                  SUBSCRIPTION_STATES, )

from core import GITHUB_HOST
from core.tasks.repository import FirstFetch
from hooks.tasks import CheckRepositoryEvents

from front.mixins.views import LinkedToUserFormViewMixin, DeferrableViewPart

from .forms import AddRepositoryForm, RemoveRepositoryForm


FakeUser = namedtuple('FakeUser', ['username'])
FakeRepository = namedtuple('FakeRepository', ['owner', 'name', 'full_name', 'no_infos', 'github_url'])


NO_REPOSITORY = '_/_'


class ToggleRepositoryBaseView(LinkedToUserFormViewMixin, FormView):
    """
    Base view to use to add/remove a repository
    """

    success_url = reverse_lazy('front:dashboard:repositories:choose')
    ajax_success_url = reverse_lazy('front:dashboard:repositories:ajax-repo')
    http_method_names = [u'post']

    def __init__(self, *args, **kwargs):
        self.repo_full_name = None
        super(ToggleRepositoryBaseView, self).__init__(*args, **kwargs)

    def form_invalid(self, form):
        """
        If the form is invalid, return to the list of repositories the user
        can add, with an error message
        """
        if 'name' in form._errors:
            self.repo_full_name = NO_REPOSITORY
        else:
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
            if not repository.first_fetch_done:
                raise Repository.DoesNotExist()
        except Repository.DoesNotExist:
            # add a job to fetch the repository
            FirstFetch.add_job(name, gh=self.request.user.get_connection())
        else:
            # If a FirstFetch is still running, do nothing more, but else...
            if repository.first_fetch_done:
                message = 'Your subscription to <strong>%s</strong> was just added'
                subscription.convert(form.can_use)
                # start fetching events (it'll be ignored if there is already a queued job)
                CheckRepositoryEvents.add_job(repository.id)

        messages.success(self.request, message % name)

        return super(AddRepositoryView, self).form_valid(form)


class RemoveRepositoryView(ToggleRepositoryBaseView):
    form_class = RemoveRepositoryForm

    def form_valid(self, form):
        name = self.repo_full_name = form.cleaned_data['name']

        form.subscription.delete()

        messages.success(self.request, 'Your subscription to <strong>%s</strong> was just removed' % name)

        return super(RemoveRepositoryView, self).form_valid(form)


class WithRepoMixin(object):

    @property
    def available_repositories(self):
        """
        Return a dict with, for each available repository for the user, the
        repository fullname as key and the "AvailableRepository" object as value
        """
        if not hasattr(self, '_available_repositories'):
            self._available_repositories = {
                ar.repository.full_name: ar
                for ar in self.request.user.available_repositories_set.all()
                                           .prefetch_related('repository__owner')
            }
        return self._available_repositories

    @property
    def subscribed_repositories(self):
        """
        Return a dict with, for each available repository for the user, the
        repository fullname as key and the "Subscription" object as value
        """
        if not hasattr(self, '_subscribed_repositories'):
            self._subscribed_repositories = {
                s.repository.full_name: s
                for s in self.request.user.subscriptions.all()
                              .prefetch_related('repository__owner')
            }
        return self._subscribed_repositories

    @property
    def waiting_subscriptions(self):
        """
        Return a dict with, for each "waiting subscriptions" of the user, the
        repository fullname as key, and the "WaitingSubscription" object as value
        """
        if not hasattr(self, '_waiting_subscriptions'):
            self._waiting_subscriptions = {
                s.repository_name: s
                for s in self.request.user.waiting_subscriptions.all()
            }

        return self._waiting_subscriptions

    @property
    def organizations(self):
        """
        Return the organizations the user belongs to
        """
        if not hasattr(self, '_organizations'):
            self._organizations = list(self.request.user.organizations.all())
        return self._organizations

    def get_organization_by_name(self, name):
        """
        Try to return an organization a user belongs to based on its name
        """
        try:
            return [o for o in self.organizations if o.username == name][0]
        except IndexError:
            return None

    def get_repository_from_full_name(self, full_name):
        """
        Return a "FakeRepository" object based on the repository's full name
        given as parameter. It contains enough data to act as a real
        repository in templates.
        If the owner of the repository doesn't exist, it will be a "FakeUser"
        """
        owner_username, repository_name = full_name.split('/')
        try:
            owner = GithubUser.objects.get(username=owner_username)
        except GithubUser.DoesNotExist:
            owner = FakeUser(
                username=owner_username,
            )
        return FakeRepository(
            name=repository_name,
            full_name=full_name,
            owner=owner,
            no_infos=True,
            github_url=GITHUB_HOST + full_name
        )

    def get_organization_and_org_name_from_name(self, name):
        """
        Based on a repository name, return:
        - the organization if there is one in ones the user belongs to
        - the organnization name, or __others__, or None
        """
        org_name = None
        org = self.get_organization_by_name(name)
        if org:
            org_name = org.username
        elif name != self.request.user.username:
            org_name = '__others__'

        return org, org_name

    def get_context_data(self, **kwargs):
        context = super(WithRepoMixin, self).get_context_data(**kwargs)

        context.update({
            'available_repositories': self.available_repositories,
            'subscribed_repositories': self.subscribed_repositories,
            'waiting_subscriptions': self.waiting_subscriptions,
            'SUBSCRIPTION_STATES': SUBSCRIPTION_STATES,
            'WAITING_SUBSCRIPTION_STATES': WAITING_SUBSCRIPTION_STATES,
            'AVAILABLE_PERMISSIONS': AVAILABLE_PERMISSIONS,
        })

        return context


class ShowRepositoryAjaxView(WithRepoMixin, TemplateView):
    template_name = 'front/dashboard/repositories/ajax_repo.html'

    def get_context_data(self, *args, **kwargs):
        context = super(ShowRepositoryAjaxView, self).get_context_data(*args, **kwargs)

        user = self.request.user

        full_name = self.kwargs['name']

        if full_name == NO_REPOSITORY:
            return context

        owner_name, repo_name = full_name.split('/')

        in_tabs = []

        # which org ?
        org, org_name = self.get_organization_and_org_name_from_name(owner_name)

        # get repository, and tabs o insert it
        try:
            repository = Repository.objects.get(
                            owner__username=owner_name,
                            name=repo_name
                        )
        except:
            # the repository doesn't exists yet
            repository = self.get_repository_from_full_name(full_name)

            # it is in the waiting list ?
            if user.waiting_subscriptions.filter(repository_name=full_name).exists():
                in_tabs.append('subscriptions')

        else:
            # we have the repository ok, check what this repo is for the user

            if user.available_repositories.filter(id=repository.id).exists():
                if org:
                    in_tabs.append('available_in_orgs')
                else:
                    in_tabs.append('available_not_in_orgs')

            if user.subscriptions.filter(repository_id=repository.id).exists():
                in_tabs.append('subscriptions')
            elif user.waiting_subscriptions.filter(repository_name=full_name).exists():
                in_tabs.append('subscriptions')

            if user.watched_repositories.filter(id=repository.id).exists():
                in_tabs.append('watched')

            if user.starred_repositories.filter(id=repository.id).exists():
                in_tabs.append('starred')

        context['group'] = {
            'name': org_name,
            'repositories': [repository],
            'organization': org,
            'in_tabs': in_tabs,
        }

        return context


class ChooseRepositoryTab(DeferrableViewPart, WithRepoMixin, TemplateView):

    template_name = 'front/dashboard/repositories/include_tab_base.html'
    deferred_template_name = 'front/dashboard/repositories/include_tab_deferred.html'
    start_deferred = True

    @property
    def part_url(self):
        return reverse_lazy('front:dashboard:repositories:choose-part-%s' % self.slug)

    def get_organization_name_for_repository(self, repository):
        """
        Returns:
            - None if the owner is the current user
            - '__others__' if the owner is neither the current user, nor in an
              organization the user belongs to
            - the name of the organization if the owner is an organization the
              user belongs to
        """
        if repository.owner.username == self.request.user.username:
            return None
        if repository.owner_id in self.organizations_ids:
            return repository.owner.username
        return '__others__'

    def order_repositories(self, repositories):
        """
        Return the list of given repositories sorted by their full name, case insensitive
        """
        return sorted(repositories, key=lambda r: r.full_name.lower())

    def order_organizations(self, organizations):
        """
        `organizations` is a list of dict, with the key `name`, the name of the
        organization. We sort this list on this name, case insensitive, letting
        `None` at first
        """
        return sorted(organizations,
                      key=lambda group: group if not group['name']
                                               else group['name'].lower())

    def sql_extra_is_self(self):
        """
        Return a dict to use in the "extra" method of a queryset to add a
        "is_self" entry (in the select part) that will be True if the selected
        repository is owned by the current user, or False
        This is meant to be used this way:
            extra = self.sql_extra_is_self()
            myqueryset.extra(**extra)
        """
        return {
            'select': {
                # used to order user owned first, then others
                'is_self': 'username!=%s',
            },
            'select_params': (self.request.user.username, ),
        }

    @property
    def organizations_ids(self):
        """
        Return the ids of organizations the user belongs to
        """
        if not hasattr(self, '_organizations_ids'):
            self._organizations_ids = [o.id for o in self.organizations]
        return self._organizations_ids

    def add_in_orgs_to_sql_extra(self, extra, table):
        """
        Add a "in_orgs" entry (in the select part) of the given "extra" dict,
        that is meant to be userd in the "extra" method of a queryset.
        This "in_orgs" value will be True if the selected repository is owned
        by an organization the current user belongs to.
        "table" is the table in the sql query to use to get the GithubUser id.
        """
        if self.organizations_ids:
            # used to order ones NOT in orgs the belongs to first
            extra['select']['in_orgs'] = ' or '.join(
                    ['%s.id=%s' % (table, org_id) for org_id in self.organizations_ids])

    def get_for_start(self, main_view, **kwargs):
        """
        Return the view as part or deferred depending on the start_deferred attr
        """
        method = 'get_as_deferred' if self.start_deferred else 'get_as_part'
        return getattr(self, method)(main_view, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ChooseRepositoryTab, self).get_context_data(**kwargs)
        context['tab'] = {'class': self.__class__}
        return context

    def get_deferred_context_data(self, **kwargs):
        context = super(ChooseRepositoryTab, self).get_deferred_context_data(**kwargs)
        context['tab'] = {'class': self.__class__}
        return context


class ChooseRepositoryTabSubscriptions(ChooseRepositoryTab):
    template_name = 'front/dashboard/repositories/include_tab_subscriptions.html'
    slug = 'subscriptions'
    url_part = 'subscriptions'
    title = 'Subscriptions'
    description = 'The list of your the respositories you subscribed.'
    start_deferred = False

    def get_context_data(self, **kwargs):
        """
        We want the subscribed repositories in groups:
        - a group with the repository the user owns
        - a group with the repository the user don't own and that are not in an
          organization he belongs to
        - one group for each organization he belongs to
        Include "waiting subscriptions" in these groups
        """
        context = super(ChooseRepositoryTabSubscriptions, self).get_context_data(**kwargs)

        extra = self.sql_extra_is_self()
        order_by = ['is_self', 'repository__owner']
        if self.organizations_ids:
            self.add_in_orgs_to_sql_extra(extra, 'T4')
            order_by.insert(0, 'in_orgs')

        context['groups'] = [
            {
                'name': org_name,
                'repositories': [sub.repository for sub in sub_list],
                'organization': self.get_organization_by_name(org_name),
            }
            for org_name, sub_list
            # group repositories by user's one, non-orgs ones, and orgs ones by org
            in groupby(
                self.request.user.subscriptions.extra(**extra)
                                # start by not in ones not in orgs, with user owns first
                               .order_by(*order_by)
                               .select_related('repository__owner'),
                lambda sub: self.get_organization_name_for_repository(sub.repository)
            )
        ]

        # add each waiting subscriptions
        for waiting_subscription in self.request.user.waiting_subscriptions.all():
            try:
                repository = waiting_subscription.repository
            except Repository.DoesNotExist:
                # if repository does not exist, create a dict to store some
                # informations in the same way as a dict, for the template
                repository = self.get_repository_from_full_name(waiting_subscription.repository_name)

            # get the correct org and org_name for this repository
            org, org_name = self.get_organization_and_org_name_from_name(repository.owner.username)

            # get and update, or create, the group for this org with the new repository
            try:
                group = [g for g in context['groups'] if g['name'] == org_name][0]
            except IndexError:
                group = {
                    'name': org_name,
                    'repositories': [repository],
                    'organization': org,
                }
                context['groups'].append(group)
            else:
                group['repositories'].append(repository)

        # sort groups by org, and repo by name
        context['groups'] = self.order_organizations(context['groups'])
        for group in context['groups']:
            group['repositories'] = self.order_repositories(group['repositories'])

        return context


class ChooseRepositoryTabAvailableNotInOrgs(ChooseRepositoryTab):
    slug = 'available_not_in_orgs'
    url_part = 'available/not-in-orgs'
    title = 'Available (yours and collabs)'
    description = 'The list of repositories you own or ones you were set as a collaborator (but not in organizations).'

    def get_context_data(self, **kwargs):
        """
        We want the available repositories for the user, that are not in
        organizations he belongs to, but with two groups:
        - one for the repository he owns
        - one for the repository he doesn't own
        """
        context = super(ChooseRepositoryTabAvailableNotInOrgs, self).get_context_data(**kwargs)

        extra = self.sql_extra_is_self()

        context['groups'] = self.order_organizations([
            {
                'name': org_name,
                'repositories': self.order_repositories([ar.repository for ar in ar_list])
            }
            for org_name, ar_list
            # group repositories by orgs ones by org
            in groupby(
                self.request.user.available_repositories_set.extra(**extra)
                                 .exclude(organization_id__in=self.organizations_ids)
                                 .select_related('is_self', 'repository__owner')
                                 .order_by('repository__owner'),
                lambda ar: self.get_organization_name_for_repository(ar.repository)
            )
        ])
        return context


class ChooseRepositoryTabAvailableInOrgs(ChooseRepositoryTab):
    slug = 'available_in_orgs'
    url_part = 'available/in-orgs'
    title = 'Available (in orgs)'
    description = 'The list of repositories of your organizations.'

    def get_context_data(self, **kwargs):
        """
        We want the available repositories for the user in organizations he
        belongs to, with one group for each organization
        """
        context = super(ChooseRepositoryTabAvailableInOrgs, self).get_context_data(**kwargs)

        context['groups'] = self.order_organizations([
            {
                'name': org_name,
                'repositories': self.order_repositories([ar.repository for ar in ar_list]),
                'organization': self.get_organization_by_name(org_name),
            }
            for org_name, ar_list
            # group repositories by orgs ones by org
            in groupby(
                self.request.user.available_repositories_set
                                 .filter(organization_id__in=self.organizations_ids)
                                 .select_related('repository__owner')
                                 .order_by('repository__owner'),
                lambda ar: ar.repository.owner.username
            )
        ])

        return context


class ChooseRepositoryTabWatched(ChooseRepositoryTab):
    slug = 'watched'
    url_part = 'watched'
    title = 'Watched on Github'
    description = 'The list of repositories you watch on Github.'

    def get_context_data(self, **kwargs):
        """
        We want the watched repositories in groups:
        - a group with the repository the user owns
        - a group with the repository the user don't own and that are not in an
          organization he belongs to
        - one group for each organization he belongs to
        """
        context = super(ChooseRepositoryTabWatched, self).get_context_data(**kwargs)

        extra = self.sql_extra_is_self()
        order_by = ['is_self', 'owner']
        if self.organizations_ids:
            self.add_in_orgs_to_sql_extra(extra, 'T4')
            order_by.insert(0, 'in_orgs')

        context['groups'] = self.order_organizations(
            [
                {
                    'name': org_name,
                    'repositories': self.order_repositories(repositories_list),
                    'organization': self.get_organization_by_name(org_name),
                }
                for org_name, repositories_list
                # group repositories by user's one, non-orgs ones, and orgs ones by org
                in groupby(
                    self.request.user.watched_repositories.extra(**extra)
                                    # start by not in ones not in orgs, with user owns first
                                   .order_by(*order_by)
                                   .select_related('owner'),
                    lambda repository: self.get_organization_name_for_repository(repository)
                )
            ],
        )

        return context


class ChooseRepositoryTabStarred(ChooseRepositoryTab):
    auto_load = False
    slug = 'starred'
    url_part = 'starred'
    title = 'Starred on Github'
    description = 'The list of repositories you starred on Github.'
    deferred_description = 'The list of repositories you starred on Github. May be long to retrieve.'

    def get_context_data(self, **kwargs):
        """
        We want all the repositories the user starred, all in the same group
        """
        context = super(ChooseRepositoryTabStarred, self).get_context_data(**kwargs)

        starred = self.order_repositories(self.request.user.starred_repositories.all())

        if len(starred):
            context['groups'] = [{
                'name': '__starred__',
                'repositories': starred,
            }]
        else:
            context['groups'] = []

        return context


class ChooseRepositoryView(TemplateView):
    template_name = 'front/dashboard/repositories/choose.html'
    url_name = 'front:dashboard:repositories:choose'

    tabs = [
        ChooseRepositoryTabSubscriptions,
        ChooseRepositoryTabAvailableNotInOrgs,
        ChooseRepositoryTabAvailableInOrgs,
        ChooseRepositoryTabWatched,
        ChooseRepositoryTabStarred,
    ]

    def get_context_data(self, **kwargs):
        from core.tasks.githubuser import FetchAvailableRepositoriesJob
        context = super(ChooseRepositoryView, self).get_context_data(**kwargs)

        if [j for j in FetchAvailableRepositoriesJob.collection(
                            identifier=self.request.user.id, queued=1).instances()
                        if j.status.hget() != STATUSES.DELAYED]:
            context['still_fetching'] = True

        context['tabs'] = [
            {
                'class': tab,
                'part': tab().get_for_start(self),
            }
            for tab in self.tabs
        ]

        return context


class AskFetchAvailableRepositories(RedirectView):
    """
    Fetch the available repositories of the current user from github then
    redirect him to the subscriptions page
    """
    permanent = False
    http_method_names = [u'post']
    url = reverse_lazy("front:dashboard:repositories:choose")

    def post(self, *args, **kwargs):
        try:
            self.request.user.fetch_all(available_only=True)
        except Exception:
            messages.error(self.request, 'The list of repositories you can subscribe to (ones you own, collaborate to, or in your organizations) could not be updated :(')
        else:
            messages.success(self.request, 'The list of repositories you can subscribe to (ones you own, collaborate to, or in your organizations) was just updated')
        return super(AskFetchAvailableRepositories, self).post(*args, **kwargs)
