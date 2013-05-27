from django.conf.urls import patterns, include
from django.views.generic.base import RedirectView

urlpatterns = patterns('',
    (r'^$', RedirectView.as_view(url='dashboard')),
    (r'^dashboard/$', include('front.dashboard.urls')),
    (r'^issues/$', include('front.issues.urls')),
    (r'^worflow/$', include('front.workflow.urls')),
    (r'^timeline/$', include('front.timeline.urls')),
)
