__all__ = [
    'FetchIssueByNumber',
    'UpdateIssueCacheTemplate',
    'IssueEditStateJob',
]

import time

from async_messages import messages

from limpyd import fields
from limpyd_jobs import STATUSES

from core.models import Issue, Repository
from core.ghpool import ApiError, ApiNotFoundError

from .base import DjangoModelJob, Job


class FetchIssueByNumber(Job):
    """
    Fetch the whole issue for a repository, given only the issue's number
    """
    queue_name = 'fetch-issue-by-number'
    deleted = fields.InstanceHashField()
    force_fetch = fields.InstanceHashField()  # will only force the issue/pr api call

    permission = 'read'

    @property
    def repository(self):
        if not hasattr(self, '_repository'):
            repository_id, issue_number = self.identifier.hget().split('#')
            self._repository = Repository.objects.get(id=repository_id)
        return self._repository

    def run(self, queue):
        """
        Fetch the issue with the given number for the current repository
        """
        super(FetchIssueByNumber, self).run(queue)

        gh = self.gh
        if not gh:
            return  # it's delayed !

        repository_id, issue_number = self.identifier.hget().split('#')

        repository = self.repository

        try:
            issue = repository.issues.get(number=issue_number)
        except Issue.DoesNotExist:
            issue = Issue(repository=repository, number=issue_number)

        force_fetch = self.force_fetch.hget() == '1'
        try:
            # prefetch full data if wanted
            if force_fetch:
                if repository.has_issues:
                    issue.fetch(gh, force_fetch=True)
                if issue.is_pull_request:
                    issue.fetch_pr(gh, force_fetch=True)

            # now the normal fetch, if we previously force fetched they'll result in 304
            issue.fetch_all(gh)
        except ApiNotFoundError, e:
            # we have a 404, but... check if it's the issue itself
            try:
                issue.fetch(gh)
            except ApiNotFoundError:
                # ok the issue doesn't exist anymore, delete id
                issue.delete()
                self.deleted.hset(1)
                return False
            else:
                raise e

        return True

    def success_message_addon(self, queue, result):
        if result is False:
            return ' [deleted]'


class IssueJob(DjangoModelJob):
    """
    Abstract job model for jobs based on the Issue model
    """
    abstract = True
    model = Issue

    @property
    def issue(self):
        if not hasattr(self, '_issue'):
            self._issue = self.object
        return self._issue

    @property
    def repository(self):
        if not hasattr(self, '_repository'):
            self._repository = self.issue.repository
        return self._repository


class UpdateIssueCacheTemplate(IssueJob):
    """
    Job that update the cached template of an issue
    """
    queue_name = 'update-issue-tmpl'

    force_regenerate = fields.InstanceHashField()
    update_duration = fields.InstanceHashField()

    def run(self, queue):
        """
        Update the cached template of the issue and save the spent duration
        """
        super(UpdateIssueCacheTemplate, self).run(queue)

        start_time = time.time()

        try:
            issue = self.issue
        except Issue.DoesNotExist:
            # the issue doesn't exist anymore, stop here
            self.status.hset(STATUSES.CANCELED)
            return False

        issue.update_saved_hash()
        issue.update_cached_template(
                                force_regenerate=self.force_regenerate.hget())

        duration = '%.2f' % ((time.time() - start_time) * 1000)

        self.update_duration.hset(duration)

        return duration

    def success_message_addon(self, queue, result):
        """
        Display the duration of the cached template update
        """
        msg = 'duration=%sms' % self.update_duration.hget()

        if self.force_regenerate.hget():
            return ' [forced=True, %s]' % msg
        else:
            return ' [%s]' % msg


class IssueEditStateJob(IssueJob):

    queue_name = 'edit-issue-state'

    permission = 'self'

    def run(self, queue):
        """
        Get the issue and update its state
        """
        super(IssueEditStateJob, self).run(queue)

        gh = self.gh
        if not gh:
            return  # it's delayed !

        try:
            issue = self.issue
        except Issue.DoesNotExist:
            # the issue doesn't exist anymore, stop here
            self.status.hset(STATUSES.CANCELED)
            messages.error(self.gh_user, 'The issue you wanted to open/close seems to have been deleted!')
            return False

        try:
            issue.dist_edit(mode='update', gh=gh, fields=['state'])
        except ApiError, e:
            message = None
            issue_state_verb = 'close' if issue.state == 'closed' else 'reopen'

            if e.code == 422:
                message = u'Github refused to %s the %s <strong>#%s</strong> on <strong>%s</strong>' % (
                    issue_state_verb, issue.type, issue.number, issue.repository.full_name)

            elif e.code in (401, 403):
                tries = self.tries.hget()
                if tries and int(tries) >= 5:
                    message = u'You seem to not have the right to %s the %s <strong>#%s</strong> on <strong>%s</strong>' % (
                        issue_state_verb, issue.type, issue.number, issue.repository.full_name)

            if message:
                messages.error(self.gh_user, message)
                try:
                    # don't use "issue" cache
                    self.object.fetch(gh, force_fetch=True)
                except Exception:
                    pass
                return None

            else:
                raise

        message = u'The %s <strong>#%d</strong> on <strong>%s</strong> was correctly %s' % (
                    issue.type,
                    issue.number,
                    issue.repository.full_name,
                    'closed' if issue.state == 'closed' else 'reopened')
        messages.success(self.gh_user, message)

        # don't use "issue" cache
        self.object.fetch_all(gh)

        return None
