from core.models import Issue

from ..views import BaseRepositoryView


class IssuesView(BaseRepositoryView):
    name = 'Issues'
    url_name = 'issues'
    template_name = 'front/repository/issues/base.html'

    def get_issues(self, repository):
        return repository.issues.filter(state='open')

    def get_context_data(self, **kwargs):
        """
        Set default content for the issue views
        """
        context = super(IssuesView, self).get_context_data(**kwargs)

        repository = context['current_repository']

        # get the list of issues
        issues = self.get_issues(repository)

        # final context
        context.update({
            'issues': issues,
        })

        return context


class IssueView(IssuesView):
    url_name = 'issue'

    def get_current_issue_for_context(self, context):
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
