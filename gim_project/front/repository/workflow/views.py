from ..views import BaseRepositoryView


class WorkflowView(BaseRepositoryView):
    name = 'Workflow'
    url_name = 'workflow'
    template_name = 'front/repository/workflow/base.html'
