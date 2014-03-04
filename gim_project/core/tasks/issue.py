__all__ = [
    'FetchIssueByNumber',
    'UpdateIssueCacheTemplate',
    'IssueEditStateJob',
    'IssueEditTitleJob',
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


class BaseIssueEditJob(IssueJob):
    abstract = True

    permission = 'self'
    editable_fields = None
    values = None

    @property
    def action_verb(self):
        return self.edit_mode

    @property
    def action_done(self):
        return self.edit_mode + 'd'

    def run(self, queue):
        """
        Get the issue and update it
        """
        super(BaseIssueEditJob, self).run(queue)

        gh = self.gh
        if not gh:
            return  # it's delayed !

        try:
            issue = self.issue
        except Issue.DoesNotExist:
            # the issue doesn't exist anymore, stop here
            self.status.hset(STATUSES.CANCELED)
            messages.error(self.gh_user, 'The issue you wanted to %s seems to have been deleted' % self.action_verb)
            return False

        try:
            issue.dist_edit(mode=self.edit_mode, gh=gh, fields=self.editable_fields, values=self.values)
        except ApiError, e:
            message = None

            if e.code == 422:
                message = u'Github refused to %s the %s <strong>#%s</strong> on <strong>%s</strong>' % (
                    self.action_verb, issue.type, issue.number, issue.repository.full_name)
                self.status.hset(STATUSES.CANCELED)

            elif e.code in (401, 403):
                tries = self.tries.hget()
                if tries and int(tries) >= 5:
                    message = u'You seem to not have the right to %s the %s <strong>#%s</strong> on <strong>%s</strong>' % (
                        self.action_verb, issue.type, issue.number, issue.repository.full_name)
                    self.status.hset(STATUSES.CANCELED)

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

        messages.success(self.gh_user, self.get_success_user_message(issue))

        # ask for frech data
        FetchIssueByNumber.add_job('%s#%s' % (issue.repository_id, issue.number), gh=gh)

        return None

    def get_success_user_message(self, issue):
        return u'The %s <strong>#%d</strong> on <strong>%s</strong> was correctly %s' % (
                    issue.type,
                    issue.number,
                    issue.repository.full_name,
                    self.action_done
                )


class IssueEditFieldJob(BaseIssueEditJob):
    abstract = True
    edit_mode = 'update'

    value = fields.InstanceHashField()

    def get_field_value(self):
        return self.value.hget()

    @property
    def values(self):
        return {
            self.editable_fields[0]: self.get_field_value()
        }

    def get_success_user_message(self, issue):
        message = super(IssueEditFieldJob, self).get_success_user_message(issue)
        return message + u' (updated: <strong>%s</strong>)' % self.editable_fields[0]


class IssueEditStateJob(IssueEditFieldJob):
    queue_name = 'edit-issue-state'
    editable_fields = ['state']

    @property
    def action_done(self):
        value = self.value.hget()
        return 'reopened' if value == 'open' else 'closed'

    @property
    def action_verb(self):
        value = self.value.hget()
        return 'reopen' if value == 'open' else 'close'

    def get_success_user_message(self, issue):
        # call the one from BaseIssueEditJob
        super(IssueEditFieldJob, self).get_success_user_message(issue)


class IssueEditTitleJob(IssueEditFieldJob):
    queue_name = 'edit-issue-title'
    editable_fields = ['title']


class IssueEditBodyJob(IssueEditFieldJob):
    queue_name = 'edit-issue-body'
    editable_fields = ['body']


class IssueEditMilestoneJob(IssueEditFieldJob):
    queue_name = 'edit-issue-milestone'
    editable_fields = ['milestone']

    def get_field_value(self):
        return self.value.hget() or None


class IssueEditAssigneeJob(IssueEditFieldJob):
    queue_name = 'edit-issue-assignee'
    editable_fields = ['assignee']

    def get_field_value(self):
        return self.value.hget() or None
