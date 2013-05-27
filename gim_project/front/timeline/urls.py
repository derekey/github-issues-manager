from django.conf.urls import patterns, url

from .views import TimelineView

urlpatterns = patterns('',
    url(r'^$', TimelineView.as_view(), name=TimelineView.url_name),
)
