from django.conf.urls import patterns, url
from django.views.generic import RedirectView
from django.core.urlresolvers import reverse_lazy

from .views import AddRepositoryView, RemoveRepositoryView, ChooseRepositoryView

urlpatterns = patterns('',
    url(r'^$', RedirectView.as_view(url=reverse_lazy("front:dashboard:home"))),
    url(r'^choose/$', ChooseRepositoryView.as_view(), name='choose'),
    url(r'^add/$', AddRepositoryView.as_view(), name='add'),
    url(r'^remove/$', RemoveRepositoryView.as_view(), name='remove'),
)
