from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View

import json

from . import EVENTS
from .models import EventManager


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

            payload = json.loads(request.POST['payload'])
            self.event_manager = EventManager(payload['repository'])
            if not self.event_manager.repository:
                return HttpResponse('Repository not managed')

            method(payload)
        except Exception:
            pass

        return HttpResponse('OK')

    def event_issues(self, payload):
        return self.event_manager.event_issues(payload['issue'])

    def event_issue_comment(self, payload):
        payload['comment']['issue'] = payload['issue']
        return self.event_manager.event_issue_comment(payload['comment'])

    def event_pull_request(self, payload):
        return self.event_manager.event_pull_request(payload['pull_request'])

    def event_pull_request_review_comment(self, payload):
        return self.event_manager.event_pull_request_review_comment(payload['comment'])

    def event_commit_comment(self, payload):
        return self.event_manager.event_commit_comment(payload['comment'])
