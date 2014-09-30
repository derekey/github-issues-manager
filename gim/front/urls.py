from django.conf.urls import patterns, include, url
from django.contrib.auth.decorators import login_required

from decorator_include import decorator_include

from gim.front.views import HomeView

urlpatterns = patterns('',
    url(r'^$', HomeView.as_view(), name='home'),
    url(r'^auth/', include('gim.front.auth.urls', namespace='auth')),
    url(r'^dashboard/', decorator_include(login_required, 'gim.front.dashboard.urls', namespace='dashboard')),
    url(r'^(?P<owner_username>[^/]+)/(?P<repository_name>[^/]+)/', decorator_include(login_required, 'gim.front.repository.urls', namespace='repository'))
)
