from django.conf.urls import patterns, url
from django.views.generic import TemplateView

from .views import AddRepositoryView

urlpatterns = patterns('',
    url(r'^$', TemplateView.as_view(template_name='front/dashboard/repositories/list.html'), name='list'),
    url(r'^choose/$', TemplateView.as_view(template_name='front/dashboard/repositories/choose.html'), name='choose'),
    url(r'^add/$', AddRepositoryView.as_view(), name='add'),
)
