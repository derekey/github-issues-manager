from django.conf.urls import patterns, include, url

from .views import DashboardHome, DashboardActivityPart

from front.activity.urls import activity_pattern

urlpatterns = patterns('',
    url(r'^$', DashboardHome.as_view(), name='home'),
    url(activity_pattern, DashboardActivityPart.as_view(), name='activity'),
    url(r'^repositories/', include('front.dashboard.repositories.urls', namespace='repositories')),
)
