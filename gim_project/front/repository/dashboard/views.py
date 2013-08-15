
from markdown import markdown

from django.db.models import Count
from django.core.urlresolvers import reverse_lazy

from ..views import BaseRepositoryView, RepositoryMixin


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

        base_issues_url = self.repository.get_issues_filter_url()
        base_non_assigned_issues_url = self.repository.get_issues_user_filter_url_for_username('assigned', 'none')
        base_someone_assigned_issues_url = self.repository.get_issues_user_filter_url_for_username('assigned', '*')

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
                    milestone.non_assigned_issues_url = '%s?milestone=%s&state=open' % (base_non_assigned_issues_url, milestone.number)

                if milestone.assigned_issues_count:
                    milestone.assigned_issues_percent = 100.0 * milestone.assigned_issues_count / milestone.issues_count
                    milestone.assigned_issues_url = '%s?milestone=%s&state=open' % (base_someone_assigned_issues_url, milestone.number)

                if milestone.closed_issues_count:
                    milestone.closed_issues_percent = 100.0 * milestone.closed_issues_count / milestone.issues_count
                    milestone.closed_issues_url = '%s?milestone=%s&state=closed' % (base_issues_url, milestone.number)

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


class DashboardView(BaseRepositoryView):
    name = 'Dashboard'
    url_name = 'dashboard'
    template_name = 'front/repository/dashboard/base.html'

    def get_context_data(self, **kwargs):
        context = super(DashboardView, self).get_context_data(**kwargs)

        context['parts'] = {}
        context['parts']['milestones'] = MilestonesPart().get_as_part(self)

        return context
