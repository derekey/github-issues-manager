from datetime import datetime

from django.conf import settings
from django.db import models

from core import models as core_models
from core.ghpool import prepare_fetch_headers, ApiError
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
