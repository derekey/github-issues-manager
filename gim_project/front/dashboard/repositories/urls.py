from django.conf.urls import patterns, url
from django.views.generic import TemplateView

from .views import AddRepositoryView, ChooseRepositoryView

urlpatterns = patterns('',
    url(r'^$', TemplateView.as_view(template_name='front/dashboard/repositories/list.html'), name='list'),
    url(r'^choose/$', ChooseRepositoryView.as_view(), name='choose'),
    url(r'^add/$', AddRepositoryView.as_view(), name='add'),
)
