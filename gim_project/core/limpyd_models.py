from datetime import datetime, timedelta
import json
from random import choice

from limpyd import model as lmodel, fields as lfields
from limpyd.contrib.collection import ExtendedCollectionManager
from limpyd_jobs.utils import datetime_to_score

from core import get_main_limpyd_database
from core.models import GithubUser


class Token(lmodel.RedisModel):

    database = get_main_limpyd_database()
    collection_manager = ExtendedCollectionManager

    username = lfields.InstanceHashField(indexable=True)
    token = lfields.InstanceHashField(unique=True)

    rate_limit_remaining = lfields.StringField()  # expirable field
    rate_limit_limit = lfields.InstanceHashField()  # hom much by hour
    rate_limit_reset = lfields.InstanceHashField()  # same as ttl(rate_limit_remaining)
    scopes = lfields.SetField(indexable=True)  # list of scopes for this token
    valid_scopes = lfields.InstanceHashField(indexable=True)  # if scopes are valid
    available = lfields.InstanceHashField(indexable=True)  # if the token is publicly available
    last_call = lfields.InstanceHashField()  # last github call, even if error
    last_call_ok = lfields.InstanceHashField()  # last github call that was not an error
    last_call_ko = lfields.InstanceHashField()  # last github call that was an error
    errors = lfields.SortedSetField()  # will store all errors

    repos_admin = lfields.SetField(indexable=True)
    repos_push = lfields.SetField(indexable=True)

    LIMIT = 500

    @property
    def user(self):
        if not hasattr(self, '_user'):
            self._user = GithubUser.objects.get(username=self.username.hget())
        return self._user

    @classmethod
    def update_token_from_gh(cls, gh, api_error):
        token, _ = Token.get_or_connect(token=gh._connection_args['access_token'])
        token.update_from_gh(gh, api_error)

    def update_from_gh(self, gh, api_error):
        """
        Will update the current token object with information from the gh object
        and the error, if not None:
        - will save current date, and one if error or not
        - save the rate_limit limit and remaining, expiring the remaining with
          the reset givent by github
        - save scopes and mark is valid or notes
        - save the api_error if given
        If the remaining call is small (< 10% of the limit), mark the token as
        unavailable and ask for a reset when they will be available
        """
        self.username.hset(gh._connection_args['username'])

        # save last calls
        now = datetime.utcnow()
        str_now = str(now)
        self.last_call.hset(str_now)
        if not api_error:
            self.last_call_ok.hset(str_now)
        else:
            self.last_call_ko.hset(str_now)
            # save the errors
            api_error_json = json.dumps({k: getattr(api_error, k, None) for k in ('request', 'response')})
            self.errors.zadd(datetime_to_score(now), api_error_json)

        # reset scopes
        if gh.x_oauth_scopes is not None:
            self.scopes.delete()
            if gh.x_oauth_scopes:
                self.scopes.sadd(*gh.x_oauth_scopes)
            self.valid_scopes.hset(int(bool(gh.x_oauth_scopes)))
            if not gh.x_oauth_scopes or 'repo' not in gh.x_oauth_scopes:
                self.available.hset(0)

        if gh.x_ratelimit_remaining != -1:
            # add rate limit remaining, clear it after reset time
            self.rate_limit_remaining.set(gh.x_ratelimit_remaining)
            if gh.x_ratelimit_reset != -1:
                self.connection.expireat(self.rate_limit_remaining.key, gh.x_ratelimit_reset)
                self.rate_limit_reset.hset(gh.x_ratelimit_reset)
            else:
                self.connection.expire(self.rate_limit_remaining.key, 3600)
                self.rate_limit_reset.hset(datetime_to_score(datetime.utcnow()+timedelta(seconds=3600)))

            # if to few requests remaining, consider it as not available for public queries
            limit = 5000 if gh.x_ratelimit_limit == -1 else gh.x_ratelimit_limit
            self.rate_limit_limit.hset(limit)
            if not gh.x_ratelimit_remaining or gh.x_ratelimit_remaining < self.LIMIT:
                self.available.hset(0)
                self.ask_for_reset_flags()
            else:
                self.available.hset(1)

    def reset_flags(self):
        """
        Will reset the flags of this token (actually only "available")
        If the token objectis not in a good state to be reset, a task to reset
        it later will be asked.
        Return False if the reset was not successful and need to be done later
        """
        # not expired yet, ask to reset flags later
        if self.connection.exists(self.rate_limit_remaining.key):
            return False

        self.rate_limit_reset.hset(0)

        # set the token available again only if it has valid scopes
        if self.valid_scopes.hget() == '1':
            self.available.hset(1)

        return True

    def get_remaining_seconds(self):
        """
        Return the time before the reset of the rate limiting
        """
        return self.connection.ttl(self.rate_limit_remaining.key)

    def ask_for_reset_flags(self):
        """
        Create a task to reset the token's flags later. But if the token is in
        a good state, reset them now instead of creating a flag
        """
        ttl = self.get_remaining_seconds()
        if ttl <= 0:
            self.rate_limit_remaining.delete()
            self.reset_flags()
        else:
            from core.tasks.tokens import ResetTokenFlags
            ResetTokenFlags.add_job(self.token.hget(), delayed_for=ttl+2)

    def get_repos_pks_with_permissions(self, *permissions):
        """
        Return a list of repositories pks for which the user as given permissions
        """
        return self.user.available_repositories_set.filter(permission__in=permissions
                                        ).values_list('repository_id', flat=True)

    def update_repos(self):
        """
        Update the repos_admin and repo_push fields with pks of repositories
        the user can admin/push
        """
        self.repos_admin.delete()
        self.repos_admin.sadd(*self.get_repos_pks_with_permissions('admin'))

        self.repos_push.delete()
        self.repos_push.sadd(*self.get_repos_pks_with_permissions('admin', 'push'))

    @classmethod
    def get_one_for_repository(cls, repository_pk, permission, available=True, sort_by='-rate_limit_remaining'):
        collection = cls.collection()
        if available:
            collection = collection.filter(available=1)
        collection = cls.collection(available=1)
        if permission == 'admin':
            collection.filter(repos_admin=repository_pk)
        elif permission == 'push':
            collection.filter(repos_push=repository_pk)
        try:
            if sort_by is None:
                token = choice(collection.instances())
            else:
                token = collection.sort(by=sort_by).instances()[0]
        except IndexError:
            return None
        else:
            return token

    @classmethod
    def get_one(cls, available=True, sort_by='-rate_limit_remaining'):
        collection = cls.collection()
        if available:
            collection = collection.filter(available=1)
        try:
            if sort_by is None:
                token = choice(collection.instances())
            else:
                token = collection.sort(by=sort_by).instances()[0]
        except IndexError:
            return None
        else:
            return token

    @property
    def gh(self):
        from .ghpool import Connection
        username, token = self.hmget('username', 'token')
        return Connection.get(username=username, access_token=token)
