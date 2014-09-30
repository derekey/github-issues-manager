from django.conf.urls import patterns, include, url
from django.views.generic.base import RedirectView

urlpatterns = patterns('',
    url(r'^$', RedirectView.as_view(url='dashboard/'), name='home'),
    url(r'^dashboard/', include('gim.front.repository.dashboard.urls')),
    url(r'^issues/', include('gim.front.repository.issues.urls')),
    url(r'^board/', include('gim.front.repository.board.urls')),
)
