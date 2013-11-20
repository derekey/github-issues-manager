from datetime import datetime

from django.conf import settings
from django.db import models


from core import models as core_models
from core.ghpool import prepare_fetch_headers, ApiError
from core.managers import SavedObjects, MODE_ALL
from core.tasks.issue import FetchIssueByNumber
from core.utils import contribute_to_model

from . import EVENTS


HOOK_INFOS = {
        'name': 'web',
        'active': True,
        'events': EVENTS,
        'config': {
            'url': settings.GITHUB_HOOK_URL,
            'content_type': 'form'
        }
    }


class _Repository(models.Model):
    class Meta:
        abstract = True

    hook_set = models.BooleanField(default=False)
    hooks_fetched_at = models.DateTimeField(blank=True, null=True)
    hooks_etag = models.CharField(max_length=64, blank=True, null=True)

    @property
    def github_callable_identifiers_for_hooks(self):
        return self.github_callable_identifiers + [
            'hooks',
        ]

    def check_hook(self, gh=None, force=False):
        if not settings.GITHUB_HOOK_URL:
            return None

        gh = gh or self.get_gh()
        if not gh:
            return None

        try:
            response_headers = {}
            request_headers = {}
            if not force:
                request_headers = prepare_fetch_headers(
                        if_modified_since=self.hooks_fetched_at,
                        if_none_match=self.hooks_etag
                    )

            hooks = self.__class__.objects.get_data_from_github(gh,
                        identifiers=self.github_callable_identifiers_for_hooks,
                        parameters={'per_page': 100},
                        request_headers=request_headers,
                        response_headers=response_headers,
                    )

        except ApiError, e:
            # if 401 or 403: no rights: exit
            # if 404: private repo not visible: exit
            # if 304: no changes: exit but return True
            if e.response:
                if e.response['code'] in (401, 403, 404):
                    return None
                elif e.response['code'] == 304:
                    return True
            raise

        try:
            hook_id = [h for h in hooks if h['name'] == 'web' and h['config']['url'] == settings.GITHUB_HOOK_URL][0]['id']
        except Exception:
            self.hook_set = False
            hook_id = None
        else:
            self.hook_set = True

        self.hooks_etag = response_headers.get('etag') or None
        self.hooks_fetched_at = datetime.utcnow()

        self.save(update_fields=['hook_set', 'hooks_etag', 'hooks_fetched_at'])

        return hook_id

    def set_hook(self, gh):
        if not settings.GITHUB_HOOK_URL:
            return None

        hook_id = self.check_hook(gh, force=True)
        method = 'patch' if hook_id else 'post'
        identifiers = self.github_callable_identifiers_for_hooks
        if hook_id:
            identifiers += [hook_id]

        gh_callable = self.__class__.objects.get_github_callable(gh, identifiers)
        return getattr(gh_callable, method)(**HOOK_INFOS)

    def remove_hook(self, gh):
        if not settings.GITHUB_HOOK_URL:
            return None

        hook_id = self.check_hook(gh, force=True)
        if hook_id:
            identifiers = self.github_callable_identifiers_for_hooks + [hook_id]
            gh_callable = self.__class__.objects.get_github_callable(gh, identifiers)
            gh_callable.delete()
            return True
        return False

contribute_to_model(_Repository, core_models.Repository)


class EventManager(object):
    def __init__(self, repository_payload):
        self.get_repository(repository_payload)

    def get_repository(self, repository_payload):
        try:
            self.repository = core_models.Repository.objects.get(github_id=repository_payload['id'])
        except Exception:
            self.repository = None
        return self.repository

    def get_defaults(self):
        return {
            'fk': {
                'repository': self.repository
            },
            'related': {
                '*': {
                    'fk': {
                        'repository': self.repository
                    }
                }
            }
        }

    def fetch_issue(self, number):
        FetchIssueByNumber.add_job(self.repository.pk, number=number)

    def event_issues(self, payload):
        try:
            result = core_models.Issue.objects.create_or_update_from_dict(
                        data=payload,
                        modes=MODE_ALL,
                        defaults=self.get_defaults(),
                        saved_objects=SavedObjects(),
                    )

            self.fetch_issue(result.number)

            return result

        except Exception:
            return None

    def event_issue_comment(self, payload):
        try:
            result = core_models.IssueComment.objects.create_or_update_from_dict(
                        data=payload,
                        modes=MODE_ALL,
                        defaults=self.get_defaults(),
                        saved_objects=SavedObjects(),
                    )

            self.fetch_issue(result.issue.number)

            return result

        except Exception:
            return None

    def event_pull_request(self, payload, defaults=None):
        try:
            defaults = self.get_defaults()
            defaults.setdefault('simple', {})['is_pull_request'] = True

            result = core_models.Issue.objects.create_or_update_from_dict(
                        data=payload,
                        modes=MODE_ALL,
                        defaults=defaults,
                        fetched_at_field='pr_fetched_at',
                        saved_objects=SavedObjects(),
                    )

            self.fetch_issue(result.number)

            return result

        except Exception:
            return None

    def event_pull_request_review_comment(self, payload):
        try:
            defaults = self.get_defaults()

            # is the issue already exists ?
            number = core_models.Issue.objects.get_number_from_url(payload['pull_request_url'])
            if not number:
                return None

            try:
                issue = self.repository.issues.get(number=number)
            except core_models.Issue.DoesNotExist:
                self.fetch_issue(number)
            else:
                defaults['fk']['issue'] = issue
                defaults.setdefault('related', {}).setdefault('issue', {}).setdefault('simple', {})['is_pull_request'] = True

                result = core_models.PullRequestComment.objects.create_or_update_from_dict(
                            data=payload,
                            modes=MODE_ALL,
                            defaults=defaults,
                            saved_objects=SavedObjects(),
                        )

                self.fetch_issue(result.issue.number)

                return result

        except Exception:
            return None
