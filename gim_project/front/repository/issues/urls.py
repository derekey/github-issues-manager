from django.conf.urls import patterns, url

from .views import IssuesView, IssueView, UserIssuesView

urlpatterns = patterns('',
    url(r'^$', IssuesView.as_view(), name=IssuesView.url_name),
    url(r'^(?P<user_filter_type>(?:assigned|created_by|closed_by))/(?P<username>[^/]+)/$', UserIssuesView.as_view(), name=UserIssuesView.url_name),
    url(r'^(?P<issue_number>\d+)/$', IssueView.as_view(), name=IssueView.url_name),
)
