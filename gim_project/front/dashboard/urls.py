from django.conf.urls import patterns, url
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView

urlpatterns = patterns('',
    url(r'^$', login_required(TemplateView.as_view(template_name='front/dashboard/home.html')), name='home'),
    url(r'^repositories/add/$', login_required(TemplateView.as_view(template_name='front/dashboard/add_repository.html')), name='add_repository'),
)
