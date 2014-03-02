from django.core.urlresolvers import reverse_lazy
from django.http import HttpResponseRedirect
from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = 'front/home.html'
    redirect_authenticated_url = reverse_lazy('front:dashboard:home')

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated():
            return HttpResponseRedirect(self.redirect_authenticated_url)
        return super(HomeView, self).get(request, *args, **kwargs)
