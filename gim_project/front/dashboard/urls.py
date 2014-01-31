from django.conf.urls import patterns, include, url

from .views import DashboardHome, DashboardActivityPart

urlpatterns = patterns('',
    url(r'^$', DashboardHome.as_view(), name='home'),
    url(r'^activity/$', DashboardActivityPart.as_view(), name='activity'),
    url(r'^repositories/', include('front.dashboard.repositories.urls', namespace='repositories')),
)
