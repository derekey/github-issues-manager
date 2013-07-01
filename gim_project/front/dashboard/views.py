from django.views.generic import ListView


from ..views import SubscribedRepositoriesMixin
from subscriptions.models import SUBSCRIPTION_STATES


class DashboardHome(SubscribedRepositoriesMixin, ListView):
    template_name = 'front/dashboard/home.html'
    url_name = 'front:dashboard:home'

    def get_context_data(self, **kwargs):
        context = super(DashboardHome, self).get_context_data(**kwargs)

        repositories = context['subscribed_repositories']
        subscription_by_repo_id = dict((s.repository_id, s) for s in self.subscriptions)

        total_counts = {
            'assigned': 0,
            'created': 0,
            'prs': 0,
            'all_prs': 0,
            'all': 0,
        }

        for repository in repositories:
            repository.user_counts_open = {
                'all_prs': repository.issues.filter(state='open',
                                                    is_pull_request=True).count(),
                'all': repository.issues.filter(state='open').count(),
            }

            repository.user_counts_open['created'] = repository.issues.filter(
                                    state='open', user=self.request.user).count()

            # count prs only if we have issues (no issues = no prs)
            if repository.user_counts_open['created']:
                repository.user_counts_open['prs'] = repository.issues.filter(
                    state='open', is_pull_request=True, user=self.request.user).count()
            else:
                repository.user_counts_open['prs'] = 0

            # count assigned only if owner or collaborator
            subscription = subscription_by_repo_id.get(repository.id, None)
            if subscription and subscription.state != SUBSCRIPTION_STATES.READ:
                repository.user_counts_open['assigned'] = repository.issues.filter(
                                    state='open', assignee=self.request.user).count()

            for key, count in repository.user_counts_open.items():
                total_counts[key] += count

        context['total_counts'] = total_counts

        context['subscription_by_repo_id'] = subscription_by_repo_id

        return context
