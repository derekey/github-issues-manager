from ..views import BaseRepositoryView


class IssuesView(BaseRepositoryView):
    name = 'Issues'
    url_name = 'issues'
    template_name = 'front/repository/issues/base.html'
