from django.conf.urls import patterns, include, url

from django.views.generic import TemplateView

urlpatterns = patterns('',
    url(r'^$', TemplateView.as_view(template_name='front/home.html'), name='home'),
    url(r'^auth/', include('front.auth.urls', namespace='auth')),
    url(r'^dashboard/', include('front.dashboard.urls', namespace='dashboard')),
    url(r'^(?P<owner_username>[^/]+)/(?P<repository_name>[^/]+)/', include('front.repository.urls', namespace='repository'))
)
