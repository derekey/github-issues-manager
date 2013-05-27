from django.conf.urls import patterns, url

from .views import WorkflowView

urlpatterns = patterns('',
    url(r'^$', WorkflowView.as_view(), name='workflow'),
)
