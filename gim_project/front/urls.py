from django.conf.urls import patterns, include, url
from django.views.generic.base import RedirectView

repository_patterns = patterns('',
    url(r'^$', RedirectView.as_view(url='dashboard'), name='repository'),
    url(r'^dashboard/$', include('front.dashboard.urls')),
    url(r'^issues/$', include('front.issues.urls')),
    url(r'^worflow/$', include('front.workflow.urls')),
    url(r'^timeline/$', include('front.timeline.urls')),
)

urlpatterns = patterns('',
    url(r'^(?P<owner_username>[^/]+)/(?P<repository_name>[^/]+)/', include(repository_patterns))
)
