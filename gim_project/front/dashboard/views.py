from django.views.generic import ListView


from ..views import SubscribedRepositoriesMixin


class DashboardHome(SubscribedRepositoriesMixin, ListView):
    template_name = 'front/dashboard/home.html'
    url_name = 'front:dashboard:home'

    def get_context_data(self, **kwargs):
        context = super(DashboardHome, self).get_context_data(**kwargs)

        repositories = context['subscribed_repositories']

        total_counts = {
            'assigned': 0,
            'created': 0,
            'prs': 0,
            'all_prs': 0,
            'all': 0,
        }

        for repository in repositories:
            repository.user_counts_open = {
                'assigned': repository.issues.filter(state='open', assignee=self.request.user).count(),
                'created': repository.issues.filter(state='open', user=self.request.user).count(),
                'prs': repository.issues.filter(state='open', is_pull_request=True, user=self.request.user).count(),
                'all_prs': repository.issues.filter(state='open', is_pull_request=True).count(),
                'all': repository.issues.filter(state='open').count(),
            }
            for key, count in repository.user_counts_open.items():
                total_counts[key] += count

        context['total_counts'] = total_counts

        return context
