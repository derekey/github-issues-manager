from django.views.generic import ListView, TemplateView
from django.core.urlresolvers import reverse_lazy

from activity.limpyd_models import RepositoryActivity
from front.activity.views import ActivityMixin
from ..views import SubscribedRepositoriesMixin, DeferrableViewPart


class DashboardActivityPart(ActivityMixin, DeferrableViewPart, SubscribedRepositoriesMixin, TemplateView):
    part_url = reverse_lazy('front:dashboard:activity')
    template_name = 'front//dashboard/include_activity.html'
    deferred_template_name = 'front/dashboard/include_activity_deferred.html'

    repository_pks = None

    def inherit_from_view(self, view):
        super(DashboardActivityPart, self).inherit_from_view(view)
        self.repository_pks = view.repository_pks

    def get_pks(self):
        return [s.repository_id for s in self.subscriptions]

    def get_context_data(self, *args, **kwargs):
        context = super(DashboardActivityPart, self).get_context_data(**kwargs)

        activity, has_more = RepositoryActivity.get_for_repositories(
                                    pks=self.repository_pks or self.get_pks(),
                                    **self.activity_arguments
                                )
        context.update({
            'activity': RepositoryActivity.load_objects(activity),
            'more_activity': has_more,
            'activity_mode': 'repositories',
        })

        return context


class DashboardHome(SubscribedRepositoriesMixin, ListView):
    template_name = 'front/dashboard/home.html'
    url_name = 'front:dashboard:home'

    def get_context_data(self, **kwargs):
        context = super(DashboardHome, self).get_context_data(**kwargs)

        repositories = context['subscribed_repositories']
        subscription_by_repo_id = dict((s.repository_id, s) for s in self.subscriptions)

        for repository in repositories:
            repository.user_counts_open = repository.counters.get_user_counts(self.request.user.pk)

        context['subscription_by_repo_id'] = subscription_by_repo_id

        self.repository_pks = subscription_by_repo_id.keys()
        context['parts'] = {
            'activity': DashboardActivityPart().get_as_deferred(self),
        }

        return context
