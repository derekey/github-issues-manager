from django.conf.urls import patterns, url

from .views import IssuesView, IssueView

urlpatterns = patterns('',
    url(r'^$', IssuesView.as_view(), name=IssuesView.url_name),
    url(r'^(?P<issue_number>\d+)/$', IssueView.as_view(), name=IssueView.url_name),
)
