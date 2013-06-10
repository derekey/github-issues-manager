from django.conf.urls import patterns, url
from django.views.generic import TemplateView

urlpatterns = patterns('',
    url(r'^$', TemplateView.as_view(template_name='front/dashboard/home.html'), name='home'),
    url(r'^repositories/add/$', TemplateView.as_view(template_name='front/dashboard/add_repository.html'), name='add_repository'),
)
