from django.conf.urls import patterns, include, url
from django.views.generic.base import RedirectView

repository_patterns = patterns('',
    (r'^$', RedirectView.as_view(url='dashboard')),
    (r'^dashboard/$', include('front.dashboard.urls')),
    (r'^issues/$', include('front.issues.urls')),
    (r'^worflow/$', include('front.workflow.urls')),
    (r'^timeline/$', include('front.timeline.urls')),
)

urlpatterns = patterns('',
    url(r'^(?P<owner_username>[^/]+)/(?P<repository_name>[^/]+)/', include(repository_patterns))
)
