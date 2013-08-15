from django.conf.urls import patterns, url

from .views import DashboardView, MilestonesPart, CountersPart

urlpatterns = patterns('',
    url(r'^$', DashboardView.as_view(), name=DashboardView.url_name),
    url(r'^milestones/$', MilestonesPart.as_view(), name=MilestonesPart.url_name),
    url(r'^counters/$', CountersPart.as_view(), name=CountersPart.url_name),
)
