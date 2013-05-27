from random import choice

from ..views import BaseRepositoryView


class IssuesView(BaseRepositoryView):
    name = 'Issues'
    url_name = 'issues'
    template_name = 'front/repository/issues/base.html'

    def get_context_data(self, **kwargs):
        """
        Set default content for the repository views:
            - list of available repositories
            - list of all main views for this repository
        """
        context = super(IssuesView, self).get_context_data(**kwargs)

        repository = context['current_repository']

        issues = repository.issues.all()
        current_issue = choice(issues)

        context.update({
            'issues': issues,
            'current_issue': current_issue
        })

        return context
