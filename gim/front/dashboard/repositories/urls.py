from django.conf.urls import patterns, url
from django.views.generic import RedirectView
from django.core.urlresolvers import reverse_lazy

from .views import (AddRepositoryView, RemoveRepositoryView,
                    ChooseRepositoryView, AskFetchAvailableRepositories,
                    ShowRepositoryAjaxView)

urlpatterns = patterns('',
    url(r'^$', RedirectView.as_view(url=reverse_lazy("front:dashboard:home"))),
    url(r'^choose/$', ChooseRepositoryView.as_view(), name='choose'),
    url(r'^add/$', AddRepositoryView.as_view(), name='add'),
    url(r'^remove/$', RemoveRepositoryView.as_view(), name='remove'),
    url(r'^ajax/repo/(?P<name>[^/]+/[^/]+)/$', ShowRepositoryAjaxView.as_view(), name='ajax-repo'),
    url(r'^ask-fetch/$', AskFetchAvailableRepositories.as_view(), name='ask-fetch'),
) + patterns('', *[
    url('^choose/part/%s/' % tab.url_part, tab.as_view(), name='choose-part-%s' % tab.slug) for tab in ChooseRepositoryView.tabs
])
