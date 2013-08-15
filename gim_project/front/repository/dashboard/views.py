
from markdown import markdown

from django.db.models import Count
from django.core.urlresolvers import reverse_lazy

from ..views import BaseRepositoryView, RepositoryMixin
from subscriptions.models import Subscription, SUBSCRIPTION_STATES


class RepositoryDashboardPartView(RepositoryMixin):

    def get_object(self, queryset=None):
        if getattr(self, 'object', None):
            return self.object
        return super(RepositoryDashboardPartView, self).get_object(queryset)

    def inherit_from_view(self, view):
        self.object = self.repository = view.repository
        self.args = view.args
        self.kwargs = view.kwargs
        self.request = view.request

    def get_as_part(self, main_view):
        self.inherit_from_view(main_view)
        response = self.get(self.request)
        response.render()
        return response.content

    def get_as_deferred(self):
        return {
            'defer_url': self.part_url
        }

    @property
    def part_url(self):
        reverse_kwargs = self.repository.get_reverse_kwargs()
        return reverse_lazy('front:repository:%s' % self.url_name, kwargs=reverse_kwargs)

    def get_context_data(self, **kwargs):
        context = super(RepositoryDashboardPartView, self).get_context_data(**kwargs)
        context.update({
            'defer_url': self.part_url,
        })
        return context


class MilestonesPart(RepositoryDashboardPartView):
    template_name = 'front/repository/dashboard/include_milestones.html'
    url_name = 'dashboard.milestones'

    def get_milestones(self):
        queryset = self.repository.milestones.all().annotate(issues_count=Count('issues'))

        if not self.request.GET.get('show-closed-milestones', False):
            queryset = queryset.filter(state='open')

        if not self.request.GET.get('show-empty-milestones', False):
            queryset = queryset.exclude(issues_count=0)

        milestones = list(reversed(queryset))

        for milestone in milestones:
            if milestone.description:
                # no way to get the html version from github :(
                milestone.description = markdown(milestone.description)

            if milestone.issues_count:
                milestone.non_assigned_issues_count = milestone.issues.filter(state='open', assignee__isnull=True).count()
                milestone.assigned_issues_count = milestone.issues.filter(state='open', assignee__isnull=False).count()
                milestone.open_issues_count = milestone.non_assigned_issues_count + milestone.assigned_issues_count
                milestone.closed_issues_count = milestone.issues_count - milestone.open_issues_count

                if milestone.non_assigned_issues_count:
                    milestone.non_assigned_issues_percent = 100.0 * milestone.non_assigned_issues_count / milestone.issues_count

                if milestone.assigned_issues_count:
                    milestone.assigned_issues_percent = 100.0 * milestone.assigned_issues_count / milestone.issues_count

                if milestone.closed_issues_count:
                    milestone.closed_issues_percent = 100.0 * milestone.closed_issues_count / milestone.issues_count

            else:
                milestone.non_assigned_issues_count = milestone.assigned_issues_count = \
                milestone.open_issues_count = milestone.closed_issues_count = 0

        return milestones

    def get_context_data(self, **kwargs):
        context = super(MilestonesPart, self).get_context_data(**kwargs)
        context.update({
            'milestones': self.get_milestones(),
            'show_closed_milestones': self.request.GET.get('show-closed-milestones', False),
            'show_empty_milestones': self.request.GET.get('show-empty-milestones', False),
        })
        return context


class CountersPart(RepositoryDashboardPartView):
    template_name = 'front/repository/dashboard/include_counters.html'
    url_name = 'dashboard.counters'

    def get_counters(self):
        counters = {}

        base_filter = self.repository.issues.filter(state='open')

        counters['all'] = base_filter.count()

        # count non assigned/prs only if we have issues (no issues = no non-assigned)
        if counters['all']:
            counters['all_na'] = base_filter.filter(assignee__isnull=True).count()
            counters['all_prs'] = base_filter.filter(is_pull_request=True).count()
        else:
            counters['all_na'] = counters['all_prs'] = 0


        counters['created'] = base_filter.filter(user=self.request.user).count()
        # Unable to actually manage more urls for than one filter on people
        # counters['created_na'] = base_filter.filter(user=self.request.user, assignee__isnull=True).count()

        # count prs only if we have issues (no issues = no prs)
        if counters['created']:
            counters['prs'] = base_filter.filter(is_pull_request=True, user=self.request.user).count()
        else:
            counters['prs'] = 0

        # count assigned only if owner or collaborator
        subscription = Subscription.objects.filter(repository=self.repository, user=self.request.user)
        if len(subscription) and subscription[0].state != SUBSCRIPTION_STATES.READ:
            counters['assigned'] = base_filter.filter(assignee=self.request.user).count()

        return counters

    def get_context_data(self, **kwargs):
        context = super(CountersPart, self).get_context_data(**kwargs)
        context.update({
            'counters': self.get_counters(),
        })
        return context


class DashboardView(BaseRepositoryView):
    name = 'Dashboard'
    url_name = 'dashboard'
    template_name = 'front/repository/dashboard/base.html'

    def get_context_data(self, **kwargs):
        context = super(DashboardView, self).get_context_data(**kwargs)

        context['parts'] = {}
        context['parts']['milestones'] = MilestonesPart().get_as_part(self)
        context['parts']['counters'] = CountersPart().get_as_part(self)

        return context
