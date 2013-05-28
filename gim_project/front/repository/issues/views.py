from django.db.models import Q

from core.models import Issue

from ..views import BaseRepositoryView
from ...utils import make_querystring


class IssuesView(BaseRepositoryView):
    name = 'Issues'
    url_name = 'issues'
    template_name = 'front/repository/issues/base.html'
    default_qs = 'state=open'

    qs_filters = ('milestone', 'state', 'labels')

    def get_issues_for_context(self, context):
        """
        Read the querystring from the context, already cut in parts,
        and check parts that can be applied to filter issues, and return
        an issues queryset ready to use
        """
        repository = context['current_repository']
        qs_parts = self.get_qs_parts(context)

        filters = {}

        # filter by state
        qs_state = qs_parts.get('state', None)
        if qs_state in ('open', 'closed'):
            filters['state'] = qs_state

        # filter by milestone
        qs_milestone = qs_parts.get('milestone', None)
        if qs_milestone and not isinstance(qs_milestone, list):
            if qs_milestone.isdigit():
                filters['milestone__number'] = qs_parts['milestone']
            elif qs_milestone == 'none':
                filters['milestone__isnull'] = True

        # the base queryset with the current filter
        queryset = repository.issues.filter(**filters)

        # now filter by labels
        qs_labels = qs_parts.get('labels', None)
        if qs_labels:
            if not isinstance(qs_labels, list):
                qs_labels = [qs_labels]
            label_ids = repository.labels.filter(name__in=qs_labels).values_list('id', flat=True)
            Qs = []
            for label_id in label_ids:
                Qs.append(Q(labels=label_id))
            if len(Qs):
                queryset = queryset.filter(*Qs)

        return queryset

    def get_context_data(self, **kwargs):
        """
        Set default content for the issue views
        """
        context = super(IssuesView, self).get_context_data(**kwargs)

        # get the list of issues
        issues = self.get_issues_for_context(context)

        # get the whole issue filter
        qs_parts = self.get_qs_parts(context)
        issues_filter = {}
        issue_filter_parts = {}
        for part in qs_parts:
            if part in self.qs_filters:
                issue_filter_parts[part] = qs_parts[part]
        if issue_filter_parts:
            issues_filter = {
                'parts': issue_filter_parts,
                'querystring': make_querystring(issue_filter_parts),
            }

        # final context
        context.update({
            'issues': issues,
            'issues_filter': issues_filter,
        })

        return context


class IssueView(IssuesView):
    url_name = 'issue'

    def get_current_issue_for_context(self, context):
        """
        Based on the informations from the context and url, try to return
        the wanted issue
        """
        issue = None
        if 'issue_number' in self.kwargs:
            repository = context['current_repository']
            issue = repository.issues.get(number=self.kwargs['issue_number'])
        return issue

    def get_context_data(self, **kwargs):
        """
        Add the selected view in the context
        """
        context = super(IssueView, self).get_context_data(**kwargs)

        # check which issue to display
        current_issue_state = 'ok'
        current_issue = None
        try:
            current_issue = self.get_current_issue_for_context(context)
        except Issue.DoesNotExist:
            current_issue_state = 'notfound'
        else:
            if not current_issue:
                current_issue_state = 'undefined'

        # final context
        context.update({
            'current_issue': current_issue,
            'current_issue_state': current_issue_state,
        })

        return context
