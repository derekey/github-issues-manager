from django.conf.urls import patterns, include, url
from django.views.generic.base import RedirectView

urlpatterns = patterns('',
    url(r'^$', RedirectView.as_view(url='dashboard'), name='home'),
    url(r'^dashboard/', include('front.repository.dashboard.urls')),
    url(r'^issues/', include('front.repository.issues.urls')),
    url(r'^worflow/', include('front.repository.workflow.urls')),
    url(r'^timeline/', include('front.repository.timeline.urls')),
)
