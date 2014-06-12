__all__ = [
    'IssueCommentEditJob',
    'PullRequestCommentEditJob',
    'SearchReferenceCommitForComment',
    'SearchReferenceCommitForPRComment',
    'SearchReferenceCommitForCommitComment',
]


from limpyd import fields
from limpyd_jobs import STATUSES
from limpyd_jobs.utils import compute_delayed_until

from async_messages import messages

from core.models import IssueComment, PullRequestComment, Commit, CommitComment
from core.ghpool import ApiError

from .base import DjangoModelJob


class IssueCommentJob(DjangoModelJob):
    """
    Abstract job model for jobs based on the IssueComment model
    """
    abstract = True
    model = IssueComment

    permission = 'self'


class CommentEditJob(IssueCommentJob):
    abstract = True

    mode = fields.InstanceHashField(indexable=True)
    created_pk = fields.InstanceHashField(indexable=True)

    def run(self, queue):
        """
        Get the comment and create/update/delete it
        """
        super(CommentEditJob, self).run(queue)

        gh = self.gh
        if not gh:
            return  # it's delayed !

        mode = self.mode.hget()

        try:
            comment = self.object
        except self.model.DoesNotExist:
            return None

        try:
            if mode == 'delete':
                comment.dist_delete(gh)
            else:
                comment = comment.dist_edit(mode=mode, gh=gh)
                if mode == 'create':
                    self.created_pk.hset(comment.pk)

        except ApiError, e:
            message = None

            if e.code == 422:
                message = u'Github refused to %s your comment on the %s <strong>#%s</strong> on <strong>%s</strong>' % (
                    mode, comment.issue.type, comment.issue.number, comment.repository.full_name)

            elif e.code in (401, 403):
                tries = self.tries.hget()
                if tries and int(tries) >= 5:
                    message = u'You seem to not have the right to %s a comment on the %s <strong>#%s</strong> on <strong>%s</strong>' % (
                        mode, comment.issue.type, comment.issue.number, comment.repository.full_name)

            if message:
                messages.error(self.gh_user, message)
                if mode == 'create':
                    comment.delete()
                else:
                    try:
                        comment.fetch(gh, force_fetch=True)
                    except ApiError:
                        pass
                return None

            else:
                raise

        message = u'Your comment on the %s <strong>#%s</strong> on <strong>%s</strong> was correctly %sd' % (
            comment.issue.type, comment.issue.number, comment.repository.full_name, mode)
        messages.success(self.gh_user, message)

        from core.tasks.issue import FetchIssueByNumber
        FetchIssueByNumber.add_job('%s#%s' % (comment.repository_id, comment.issue.number), gh=gh)

        return None

    def success_message_addon(self, queue, result):
        """
        Display the action done (created/updated/deleted)
        """
        return ' [%sd]' % self.mode.hget()


class IssueCommentEditJob(CommentEditJob):
    queue_name = 'edit-issue-comment'
    model = IssueComment


class PullRequestCommentEditJob(CommentEditJob):
    queue_name = 'edit-pr-comment'
    model = PullRequestComment


class SearchReferenceCommitForComment(IssueCommentJob):
    """
    When an comment references a commit, we may not have it, so we'll
    wait because it may have been fetched after the comment was received
    """

    queue_name = 'search-ref-commit-comment'

    repository_id = fields.InstanceHashField()
    commit_sha = fields.InstanceHashField()
    nb_tries = fields.InstanceHashField()

    def run(self, queue):
        super(SearchReferenceCommitForComment, self).run(queue)

        repository_id, commit_sha = self.hmget('repository_id', 'commit_sha')

        try:
            # try to find the matching commit
            Commit.objects.filter(
                repository_id=repository_id,
                sha__startswith=commit_sha,
            ).order_by('-authored_at')[0]
        except IndexError:
            # the commit was not found

            tries = int(self.nb_tries.hget() or 0)

            if tries >= 5:
                # enough tries, stop now
                self.status.hset(STATUSES.CANCELED)
                return None
            else:
                # we'll try again...
                self.status.hset(STATUSES.DELAYED)
                self.delayed_until.hset(compute_delayed_until(delayed_for=60*tries))
                self.nb_tries.hincrby(1)
            return False

        # commit found, save the comment
        self.object.save()

        return True


class SearchReferenceCommitForPRComment(SearchReferenceCommitForComment):
    model = PullRequestComment
    queue_name = 'search-ref-commit-pr-comment'


class SearchReferenceCommitForCommitComment(SearchReferenceCommitForComment):
    model = CommitComment
    queue_name = 'search-ref-commit-commit-comment'
