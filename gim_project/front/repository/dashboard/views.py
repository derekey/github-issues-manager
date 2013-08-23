
from itertools import groupby
from operator import attrgetter, itemgetter

from markdown import markdown

from django.db.models import Count
from django.core.urlresolvers import reverse_lazy
from django.views.generic import UpdateView
from django.template.response import TemplateResponse

from subscriptions.models import Subscription, SUBSCRIPTION_STATES
from core.models import LabelType
from ..views import BaseRepositoryView, RepositoryMixin, LinkedToRepositoryFormView
from .forms import LabelTypeEditForm


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


class GroupLabels(object):

    def group_labels(self, labels):

        groups = [
            (
                label_type,
                sorted(labels, key=lambda l: l.name.lower())
            )
            for label_type, labels
            in groupby(
                labels,
                attrgetter('label_type')
            )
        ]

        if len(groups) > 1 and groups[0][0] is None:
            groups = groups[1:] + groups[:1]

        return groups


class LabelsPart(RepositoryDashboardPartView, GroupLabels):
    template_name = 'front/repository/dashboard/include_labels.html'
    url_name = 'dashboard.labels'

    issues_count_subquery = """
        SELECT COUNT(*)
            FROM core_issue
                INNER JOIN core_issue_labels
                    ON core_issue.id = core_issue_labels.issue_id
            WHERE
                core_issue_labels.label_id = core_label.id
                AND
                state = 'open'
    """

    def get_labels_groups(self):
        extra = {
            'select': {'issues_count': self.issues_count_subquery},
        }

        if not self.request.GET.get('show-empty-labels', False):
            extra['where'] = ['issues_count > 0']

        labels_with_count = self.repository.labels.extra(
                                        **extra).select_related('label_type')

        return self.group_labels(labels_with_count)

    def get_context_data(self, **kwargs):
        context = super(LabelsPart, self).get_context_data(**kwargs)

        reverse_kwargs = self.repository.get_reverse_kwargs()

        context.update({
            'show_empty_labels': self.request.GET.get('show-empty-labels', False),
            'labels_groups': self.get_labels_groups(),
            'without_labels': self.repository.issues.filter(
                                    state='open', labels__isnull=True).count(),
            'labels_editor_url': reverse_lazy(
                'front:repository:%s' % LabelsEditor.url_name, kwargs=reverse_kwargs),
        })

        return context


class DashboardView(BaseRepositoryView):
    name = 'Dashboard'
    url_name = 'dashboard'
    template_name = 'front/repository/dashboard/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super(DashboardView, self).get_context_data(**kwargs)

        context['parts'] = {
            'milestones': MilestonesPart().get_as_part(self),
            'counters': CountersPart().get_as_part(self),
            'labels': LabelsPart().get_as_part(self),
        }

        return context


class LabelsEditor(BaseRepositoryView, GroupLabels):
    name = 'Labels Editor'
    url_name = 'dashboard.labels.editor'
    template_name = 'front/repository/dashboard/labels-editor/base.html'
    display_in_menu = False
    label_type_include_template = 'front/repository/dashboard/labels-editor/include-label-type.html'

    def get_labels_groups(self):
        return self.group_labels(self.repository.labels.all())

    def get_context_data(self, **kwargs):
        context = super(LabelsEditor, self).get_context_data(**kwargs)

        context.update({
            'labels_groups': self.get_labels_groups(),
            'all_labels': self.repository.labels.order_by('name').values_list('name', flat=True),
            'label_type_include_template': self.label_type_include_template,
        })

        return context


class LabelTypeFormBaseView(LinkedToRepositoryFormView, UpdateView):
    model = LabelType
    pk_url_kwarg = 'label_type_id'
    form_class = LabelTypeEditForm


class LabelTypeEdit(LabelTypeFormBaseView):
    url_name = 'dashboard.labels.editor.label_type.edit'
    template_name = 'front/repository/dashboard/labels-editor/label-type-edit.html'

    def get_context_data(self, **kwargs):
        context = super(LabelTypeEdit, self).get_context_data(**kwargs)

        reverse_kwargs = self.repository.get_reverse_kwargs()
        context['preview_url'] = reverse_lazy(
                'front:repository:%s' % LabelTypePreview.url_name, kwargs=reverse_kwargs)

        return context

    def form_valid(self, form):
        """
        Return the html block to use on the main page
        """
        self.object = form.save()

        context = {
            'label_type': self.object,
            'labels': self.object.labels.all(),
            'just_edited': True,
        }

        return TemplateResponse(
                    self.request,
                    LabelsEditor.label_type_include_template,
                    context
                )


class LabelTypePreview(LabelTypeFormBaseView):
    url_name = 'dashboard.labels.editor.label_type.edit'
    template_name = 'front/repository/dashboard/labels-editor/label-type-preview.html'
    http_method_names = [u'post']

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        return LabelType(repository=self.repository)

    def form_invalid(self, form):
        context = {
            'form': form,
            'error': True,
        }
        return self.render_to_response(context)

    def form_valid(self, form):
        context = {
            'form': form,
            'error': False
        }

        labels = self.repository.labels.order_by('name')

        matching_labels = []
        has_order = True

        for label in labels:
            if self.object.match(label.name):
                typed_name, order = self.object.get_name_and_order(label.name)
                label_data = {
                    'name': label.name,
                    'typed_name': typed_name,
                    'color': label.color,
                }
                if order is None:
                    has_order = False
                else:
                    label_data['order'] = order

                matching_labels.append(label_data)

        matching_labels.sort(key=itemgetter('order' if has_order else 'typed_name'))

        context['matching_labels'] = matching_labels

        return self.render_to_response(context)
