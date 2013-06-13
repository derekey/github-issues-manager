from django.views.generic import ListView


from ..views import SubscribedRepositoriesMixin


class DashboardHome(SubscribedRepositoriesMixin, ListView):
    template_name = 'front/dashboard/home.html'
