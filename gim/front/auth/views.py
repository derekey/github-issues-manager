import base64
from random import random

from django.views.generic import RedirectView
from django.conf import settings
from django.core.urlresolvers import reverse, reverse_lazy, resolve
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages

from limpyd_jobs import STATUSES

from gim.core.ghpool import Connection
from gim.core.models import GithubUser
from gim.core.tasks.githubuser import FetchAvailableRepositoriesJob


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

        return Connection(**params)


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
            return False, "Unexpected request, please retry"
        del self.request.session['github-auth-state']

        state = self.request.GET.get('state', None)
        if state.strip() != attended_state.strip():
            return False, "Unexpected request, please retry"

        # get code
        code = self.request.GET.get('code', None)
        if not code:
            return False, "Authentication denied, please retry"

        # get the token for the given code
        try:
            gh = self.get_github_connection()
            token = gh.get_access_token(code)
        except:
            token = None

        if not token:
            return False, "Authentication failed, please retry"

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
            user_infos = Connection(access_token=token).user.get()
        except:
            user_infos = None

        if not user_infos:
            return False, "Cannot get user informations, please retry"

        # create/update and get a user with the given infos and token
        try:
            user = GithubUser.objects.create_or_update_from_dict(
                                        data=user_infos,
                                        defaults={'simple': {'token': token}})
        except:
            return False, "Cannot save user informations, please retry"

        # reject banned users
        if not user.is_active:
            return False, "This account has been deactivated"

        # authenticate the user (needed to call login later)
        user = authenticate(username=user.username, token=user.token)
        if not user:
            return False, "Final authentication failed, please retry"

        # and finally login
        login(self.request, user)

        # set its username to the token
        user.token_object.username.hset(user.username)

        # remove other tokens for this username
        from gim.core.limpyd_models import Token
        for user_token in list(Token.collection(username=user.username).instances()):
            if user_token.token.hget() != token:
                user_token.delete()

        # add a job to fetch available repositories
        job = FetchAvailableRepositoriesJob.add_job(user.id, inform_user=1)

        if job.status == STATUSES.DELAYED:
            return True, "Authentication successful, welcome back!"
        else:
            return True, "Authentication successful, we are currently fetching repositories you can subscribe to (ones you own, collaborate to, or in your organizations)"

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
