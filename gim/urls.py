from django.conf.urls import patterns, include, url

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^', include('gim.front.urls', namespace='front', app_name='front')),

    url(r'^core-admin/', include(admin.site.urls)),
    url(r'^hooks/', include('gim.hooks.urls', namespace='hooks')),
    url(r'^graphs/', include('gim.graphs.urls', namespace='graphs')),
    url(r'^', include('gim.front.urls', namespace='front', app_name='front')),
)
