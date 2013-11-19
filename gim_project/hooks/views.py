from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View

import json

from core.models import Repository, Issue, IssueComment, PullRequestComment
from core.managers import SavedObjects, MODE_ALL
from core.tasks.issue import FetchIssueByNumber

from . import EVENTS


class GithubWebHook(View):
    http_method_names = [u'post', u'head', ]

    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        return super(GithubWebHook, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # type of event from gthub
        event = request.META['HTTP_X_GITHUB_EVENT']

        if event not in EVENTS:
            return HttpResponse('Event not allowed')

        method = getattr(self, 'event_%s' % event, None)
        if method is None:
            return HttpResponse('Event not managged')

        try:
            # pass the paylaod to a method depending of the event
            method(json.loads(request.POST['payload']))
        except:
            pass

        return HttpResponse('OK')

    def get_repository(self, repository_payload):
        try:
            self.repository = Repository.objects.get(github_id=repository_payload['id'])
        except Exception:
            self.repository = None
        return self.repository

    def get_defaults(self, payload):
        self.get_repository(payload['repository'])
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
        # url = payload['issue']['url']
        try:
            payload['issue']['repository'] = payload['repository']

            result = Issue.objects.create_or_update_from_dict(
                        data=payload['issue'],
                        modes=MODE_ALL,
                        defaults=self.get_defaults(payload),
                        saved_objects=SavedObjects(),
                    )

            self.fetch_issue(result.number)

            return result

        except Exception:
            return None

    def event_issue_comment(self, payload):
        # url = payload['comment']['url']
        try:
            payload['comment']['issue'] = payload['issue']
            payload['comment']['issue']['repository'] = payload['repository']

            result = IssueComment.objects.create_or_update_from_dict(
                        data=payload['comment'],
                        modes=MODE_ALL,
                        defaults=self.get_defaults(payload),
                        saved_objects=SavedObjects(),
                    )

            self.fetch_issue(result.issue.number)

            return result

        except Exception:
            return None

    def event_pull_request(self, payload):
        # url = payload['pull_request']['url']
        try:
            payload['pull_request']['repository'] = payload['repository']

            defaults = self.get_defaults(payload)
            defaults.setdefault('simple', {})['is_pull_request'] = True

            result = Issue.objects.create_or_update_from_dict(
                        data=payload['pull_request'],
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
        # url = payload['comment']['url']
        try:
            defaults = self.get_defaults(payload)

            # is the issue already exists ?
            number = Issue.objects.get_number_from_url(payload['comment']['pull_request_url'])
            if not number:
                return None

            try:
                issue = defaults['fk']['repository'].issues.get(number=number)
            except Issue.DoesNotExist:
                self.fetch_issue(number)
            else:
                defaults['fk']['issue'] = issue
                defaults.setdefault('related', {}).setdefault('issue', {}).setdefault('simple', {})['is_pull_request'] = True

                result = PullRequestComment.objects.create_or_update_from_dict(
                            data=payload['comment'],
                            modes=MODE_ALL,
                            defaults=defaults,
                            saved_objects=SavedObjects(),
                        )

                self.fetch_issue(result.issue.number)

                return result

        except Exception:
            return None