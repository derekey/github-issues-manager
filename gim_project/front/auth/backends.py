from django.contrib.auth.backends import ModelBackend

from core.models import GithubUser


class GithubBackend(ModelBackend):

    def authenticate(self, username=None, token=None, **kwargs):
        if not username or not token:
            return None
        try:
            return GithubUser.objects.get(username=username, token=token)
        except GithubUser.DoesNotExist:
            return None
