from django.conf.urls import patterns, include, url
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required

from decorator_include import decorator_include

urlpatterns = patterns('',
    url(r'^$', TemplateView.as_view(template_name='front/home.html'), name='home'),
    url(r'^auth/', include('front.auth.urls', namespace='auth')),
    url(r'^dashboard/', decorator_include(login_required, 'front.dashboard.urls', namespace='dashboard')),
    url(r'^(?P<owner_username>[^/]+)/(?P<repository_name>[^/]+)/', decorator_include(login_required, 'front.repository.urls', namespace='repository'))
)
