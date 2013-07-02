from django.conf.urls import patterns, url

from .views import DashboardView, MilestonesPart

urlpatterns = patterns('',
    url(r'^$', DashboardView.as_view(), name=DashboardView.url_name),
    url(r'^milestones/$', MilestonesPart.as_view(), name=MilestonesPart.url_name),
)
