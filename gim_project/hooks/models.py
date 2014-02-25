from datetime import datetime

from django.conf import settings
from django.db import models

from core import models as core_models
from core.ghpool import prepare_fetch_headers, ApiError, Connection
from core.managers import SavedObjects, MODE_ALL
from core.tasks.issue import FetchIssueByNumber
from core.utils import contribute_to_model

from . import EVENTS


HOOK_INFOS = {
        'name': 'web',
        'active': True,
        'events': EVENTS.keys(),
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
    events_fetched_at = models.DateTimeField(blank=True, null=True)
    events_etag = models.CharField(max_length=64, blank=True, null=True)

    @property
    def github_callable_identifiers_for_hooks(self):
        return self.github_callable_identifiers + [
            'hooks',
        ]

    @property
    def github_callable_identifiers_for_events(self):
        return self.github_callable_identifiers + [
            'events',
        ]

    def simple_list_fetch(self, meta_base_name, identifiers, gh=None,
                     force_fetch=True, request_headers=None,
                     response_headers=None, parameters=None):
        """
        Will fetch a list of data from the github API for the given identifiers.
        The %s_etag and %s_fetched_at fields will be updated, using
        meta_base_name to find the field that must exists. These fields will be
        used as headers for the request to avoid downloading data if there is
        no changes, except if force_fetch is True.
        This method return three things:
        - the http code received
        - the data fetched (None if we'we got qa 304)
        - the fields (of self) updated (%s_fetched_at and perhaps %s_etag)
        """

        gh = gh or self.get_gh()
        if not gh:
            return None, None, None

        if request_headers is None:
            request_headers = {}
        if response_headers is None:
            response_headers = {}
        if parameters is None:
            parameters = {}

        fetched_at_field = '%s_fetched_at' % meta_base_name
        etag_field = '%s_etag' % meta_base_name

        response_code = 200

        if not force_fetch:
            request_headers.update(prepare_fetch_headers(
                    if_modified_since=getattr(self, fetched_at_field),
                    if_none_match=getattr(self, etag_field)
                ))

        updated_fields = [fetched_at_field]

        try:
            data = self.__class__.objects.get_data_from_github(gh,
                        identifiers=identifiers,
                        parameters=parameters,
                        request_headers=request_headers,
                        response_headers=response_headers,
                    )
        except ApiError, e:
            if e.response and e.response['code'] == 304:
                response_code = 304
                setattr(self, fetched_at_field, datetime.utcnow())
                data = None
            else:
                raise
        else:
            setattr(self, etag_field, response_headers.get('etag') or None)
            setattr(self, fetched_at_field, datetime.utcnow())
            updated_fields.append(etag_field)

        return response_code, data, updated_fields

    def check_events(self, gh, force=False):
        """
        Check events for the repository. If there is new that are managed,
        get the data and create a task to fully fetch the issue
        Return the "X-Poll-Interval" from Github, to know when github will allow
        us to do this check again
        Note that we only fetch the first page (30 events max)
        """
        min_date = self.events_fetched_at
        response_headers = {}  # used to get X-Poll-Interval

        issues_to_fetch = set()
        event_manager = None

        code, events, updated_fields = self.simple_list_fetch(
                    gh=gh,
                    meta_base_name='events',
                    identifiers=self.github_callable_identifiers_for_events,
                    force_fetch=force,
                    response_headers=response_headers,
                )

        if code != 304 and events:
            event_manager = EventManager(repository=self)
            # will be set to the date of last (first in list) event
            self.events_fetched_at = None

            # fetch events in the reverse order (oldest first) to let use create
            # our own events in the correct order
            for event in reversed(events):
                if 'created_at' not in event:
                    continue
                event_date = self.events_fetched_at = Connection.parse_date(event['created_at'])
                if 'created_at' not in event or 'type' not in event or 'repo' not in event:
                    continue
                if event['type'] not in EVENTS.values():
                    continue
                if min_date and not force and event_date < min_date:
                    # not readched the min date, continue until a good one
                    continue
                try:
                    if event['type'] == 'IssuesEvent':
                        issue = event_manager.event_issues(event['payload']['issue'],
                                                           fetch_issue=False)
                        if issue:
                            issues_to_fetch.add(issue.number)
                    elif event['type'] == 'IssueCommentEvent':
                        event['payload']['comment']['issue'] = event['payload']['issue']
                        comment = event_manager.event_issue_comment(event['payload']['comment'],
                                                                     fetch_issue=False)
                        if comment:
                            issues_to_fetch.add(comment.issue.number)
                    elif event['type'] == 'PullRequestEvent':
                        issue = event_manager.event_pull_request(event['payload']['pull_request'],
                                                                 fetch_issue=False)
                        if issue:
                            issues_to_fetch.add(issue.number)
                    elif event['type'] == 'PullRequestReviewCommentEvent':
                        comment = event_manager.event_pull_request_review_comment(event['payload']['comment'],
                                                                                  fetch_issue=False)
                        if comment:
                            issues_to_fetch.add(comment.issue.number)

                except Exception:
                    raise
                    # we don't care if we cannot manage an event, the full repos
                    # will be fetched soon...
                    pass

            for number in issues_to_fetch:
                event_manager.fetch_issue(number)

        if updated_fields:
            self.save(update_fields=updated_fields)

        try:
            delay = int(response_headers['x-poll-interval'])
        except Exception:
            delay = 60

        return (len(issues_to_fetch), delay)

    def check_hook(self, gh=None, force=False):
        """
        Check if the github hook is set and if True returns the hook github ID,
        or None.
        If force is False and github returned us a 304, return True to tell "yes
        the hook is set"
        """
        if not settings.GITHUB_HOOK_URL:
            return None

        try:
            code, hooks, updated_fields = self.simple_list_fetch(
                        meta_base_name='hooks',
                        gh=gh,
                        identifiers=self.github_callable_identifiers_for_hooks,
                        force_fetch=force,
                        parameters={'per_page': 100}
                    )
        except ApiError, e:
            # if 401 or 403: no rights: exit
            # if 404: private repo not visible: exit
            if e.response and e.response['code'] in (401, 403, 404):
                    return None
            raise

        if code == 304:
            hook_id = True
        else:
            updated_fields.append('hook_set')
            try:
                hook_id = [h for h in hooks if h['name'] == 'web' and h['config']['url'] == settings.GITHUB_HOOK_URL][0]['id']
            except Exception:
                self.hook_set = False
                hook_id = None
            else:
                self.hook_set = True

        self.save(update_fields=updated_fields)

        return hook_id

    def set_hook(self, gh):
        """
        Create or update the github hook
        """
        if not settings.GITHUB_HOOK_URL:
            return None

        hook_id = self.check_hook(gh, force=True)
        method = 'patch' if hook_id else 'post'
        identifiers = self.github_callable_identifiers_for_hooks
        if hook_id:
            identifiers += [hook_id]

        gh_callable = self.__class__.objects.get_github_callable(gh, identifiers)
        hook_data = getattr(gh_callable, method)(**HOOK_INFOS)

        self.hook_set = True
        self.save(update_fields=['hook_set'])

        return hook_data

    def remove_hook(self, gh):
        """
        Remove the hook if its set
        """
        if not settings.GITHUB_HOOK_URL:
            return None

        hook_id = self.check_hook(gh, force=True)
        if hook_id:
            identifiers = self.github_callable_identifiers_for_hooks + [hook_id]
            gh_callable = self.__class__.objects.get_github_callable(gh, identifiers)
            gh_callable.delete()

            self.hook_set = False
            self.save(update_fields=['hook_set'])

            return True

        return False

contribute_to_model(_Repository, core_models.Repository)


class EventManager(object):
    def __init__(self, repository_payload=None, repository=None):
        if repository is not None:
            self.repository = repository
        else:
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
        FetchIssueByNumber.add_job('%s#%s' % (self.repository.pk, number), force_fetch=1)

    def event_issues(self, payload, fetch_issue=True):
        try:
            result = core_models.Issue.objects.create_or_update_from_dict(
                        data=payload,
                        modes=MODE_ALL,
                        defaults=self.get_defaults(),
                        saved_objects=SavedObjects(),
                    )

            if fetch_issue:
                self.fetch_issue(result.number)

            return result

        except Exception:
            return None

    def event_issue_comment(self, payload, fetch_issue=True):
        try:
            result = core_models.IssueComment.objects.create_or_update_from_dict(
                        data=payload,
                        modes=MODE_ALL,
                        defaults=self.get_defaults(),
                        saved_objects=SavedObjects(),
                    )

            if fetch_issue:
                self.fetch_issue(result.issue.number)

            return result

        except Exception:
            return None

    def event_pull_request(self, payload, fetch_issue=True):
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

            if fetch_issue:
                self.fetch_issue(result.number)

            return result

        except Exception:
            return None

    def event_pull_request_review_comment(self, payload, fetch_issue=True):
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

                if fetch_issue:
                    self.fetch_issue(result.issue.number)

                return result

        except Exception:
            return None

    def event_push(self, payload, fetch_issue=True):
        """
        When a PushEvent is received, check if we have pull requests on the
        branch the push was done, and if yes, update them
        """
        if 'ref' not in payload:
            return None

        label = ':%s' % payload['ref'][11:]  # remove "refs/heads/"

        numbers = set(self.repository.issues.filter(
                     models.Q(head_label__endswith=label) | models.Q(base_label__endswith=label),
                    is_pull_request=True
                ).values_list('number', flat=True))

        for number in numbers:
            self.fetch_issue(number)


from .tasks import *
