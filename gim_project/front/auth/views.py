import base64
from random import random

from github import GitHub

from django.views.generic import RedirectView
from django.conf import settings
from django.core.urlresolvers import reverse, reverse_lazy, resolve
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages

from core.models import GithubUser


class BaseGithubAuthView(RedirectView):
    permanent = False
    http_method_names = [u'get']

    def get_github_connection(self):
        params = dict(
            client_id = settings.GITHUB_CLIENT_ID,
            client_secret = settings.GITHUB_CLIENT_SECRET,
            scope = settings.GITHUB_SCOPE
        )
        redirect_uri = getattr(self, 'redirect_uri', None)
        if redirect_uri:
            params['redirect_uri'] = redirect_uri

        return GitHub(**params)


class LoginView(BaseGithubAuthView):
    permanent = False
    http_method_names = [u'get']

    @property
    def redirect_uri(self):
        uri = self.request.build_absolute_uri(reverse('front:auth:confirm'))
        next = self.request.GET.get('next', None)
        if next:
            uri += '?next=' + next
        return uri

    def get_redirect_url(self):
        state = self.request.session['github-auth-state'] = base64.encodestring('%s' % random())
        gh = self.get_github_connection()
        url = gh.authorize_url(state)
        return url


class ConfirmView(BaseGithubAuthView):

    def complete_auth(self):
        # check state
        attended_state = self.request.session.get('github-auth-state', None)
        if not attended_state:
            return False, "Unexpected request"
        del self.request.session['github-auth-state']

        state = self.request.GET.get('state', None)
        if state != attended_state:
            return False, "Unexpected request"

        # get code
        code = self.request.GET.get('code', None)
        if not code:
            return False, "Authentication denied"

        # get the token for the given code
        try:
            gh = self.get_github_connection()
            token = gh.get_access_token(code)
        except:
            token = None

        if not token:
            return False, "Authentication failed"

        # do we have a user for this token ?
        try:
            user_with_token = GithubUser.objects.get(token=token)
        except GithubUser.DoesNotExist:
            user_with_token = None
        else:
            user_with_token.token = None
            user_with_token.save(update_fields=['token'])

        # get informations about this user
        try:
            user_infos = GitHub(access_token=token).user.get()
        except:
            user_infos = None

        if not user_infos:
            return False, "Cannot get user informations"

        # get a user with the username
        try:
            user = GithubUser.objects.create_or_update_from_dict(user_infos)
        except:
            return False, "Cannot save user informations"

        # reject banned users
        if not user.is_active:
            return False, "This account has been deactivated"

        # authenticate the user (needed to call login later)
        user = authenticate(username=user.username, token=user.token)
        if not user:
            return False, "Final authentication failed"

        # and finally login
        login(self.request, user)

        return True, "Authentication successful"

    def get_redirect_url(self):
        auth_valid, message = self.complete_auth()

        if auth_valid:
            messages.success(self.request, message)

            next = self.request.GET.get('next', None)
            if next:
                try:
                    # ensure we're going to a valid internal address
                    resolve(next)
                except:
                    next = None

            if not next:
                next = reverse('front:dashboard:home')

            return next

        else:
            messages.error(self.request, message)
            return reverse('front:home')


class LogoutView(RedirectView):
    permanent = False
    http_method_names = [u'get']

    url = reverse_lazy('front:home')

    def get_redirect_url(self):
        logout(self.request)
        return super(LogoutView, self).get_redirect_url()
