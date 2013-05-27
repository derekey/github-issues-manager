from django.conf.urls import patterns, include, url

urlpatterns = patterns('',
    url(r'^(?P<owner_username>[^/]+)/(?P<repository_name>[^/]+)/', include('front.repository_urls'))
)
