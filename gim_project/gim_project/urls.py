from django.conf.urls import patterns, include, url

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'gim_project.views.home', name='home'),
    # url(r'^gim_project/', include('gim_project.foo.urls')),
    url(r'^', include('front.urls', namespace='front', app_name='front')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # url(r'^admin/', include(admin.site.urls)),
    url(r'^hooks/', include('hooks.urls', namespace='hooks')),
    url(r'^', include('front.urls', namespace='front', app_name='front')),
)
