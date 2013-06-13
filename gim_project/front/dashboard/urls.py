from django.conf.urls import patterns, include, url

from .views import DashboardHome

urlpatterns = patterns('',
    url(r'^$', DashboardHome.as_view(), name='home'),
    url(r'^repositories/', include('front.dashboard.repositories.urls', namespace='repositories')),
)
