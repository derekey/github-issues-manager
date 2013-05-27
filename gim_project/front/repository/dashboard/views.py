from ..views import BaseRepositoryView


class DashboardView(BaseRepositoryView):
    name = 'Dashboard'
    url_name = 'dashboard'
    template_name = 'front/repository/dashboard/base.html'
