from django.conf.urls import patterns, url

from .views import GithubWebHook

urlpatterns = patterns('',
    url(r'^github/web/', GithubWebHook.as_view(), name='github_web'),
)
