from django.conf.urls import patterns, url

from .views import IssuesView

urlpatterns = patterns('',
    url(r'^$', IssuesView.as_view(), name=IssuesView.url_name),
)
