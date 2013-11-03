from limpyd import fields
from async_messages import messages

from core.models import IssueComment
from core.ghpool import ApiError

from . import DjangoModelJob


class IssueCommentJob(DjangoModelJob):
    """
    Abstract job model for jobs based on the IssueComment model
    """
    abstract = True
    model = IssueComment


class IssueCommentEditJob(IssueCommentJob):

    queue_name = 'edit-issue-comment'

    mode = fields.InstanceHashField()

    def run(self, queue):
        """
        Get the comment and create/update/delete it
        """
        super(IssueCommentEditJob, self).run(queue)

        mode = self.mode.hget()
        gh = self.gh

        try:
            comment = self.object
        except IssueComment.DoesNotExist:
            return None

        issue_type = 'pull request' if comment.issue.is_pull_request else 'issue'

        try:
            if mode == 'delete':
                comment.dist_delete(gh)
            else:
                comment.dist_edit(mode=mode, gh=gh)

        except ApiError, e:
            message = None

            if e.code == 422:
                message = u'Github refused to %s your comment on the %s <strong>#%s</strong> on <strong>%s</strong>' % (
                    mode, issue_type, comment.issue.number, comment.repository.full_name)
                comment.delete()

            elif e.code in (401, 403):
                tries = self.tries.hget()
                if tries and int(tries) >= 5:
                    message = u'You seem to not have the right to %s a comment on the %s <strong>#%s</strong> on <strong>%s</strong>' % (
                        mode, issue_type, comment.issue.number, comment.repository.full_name)
                    comment.delete()

            if message:
                messages.error(self.gh_user, message)
                return None

            else:
                raise

        message = u'Your comment on the %s <strong>#%s</strong> on <strong>%s</strong> was correctly %sd' % (
            issue_type, comment.issue.number, comment.repository.full_name, mode)
        messages.success(self.gh_user, message)

        self.object.issue.fetch_all(gh)

        return None

    def success_message_addon(self, queue, result):
        """
        Display the action done (created/updated/deleted)
        """
        return ' [%sd]' % self.mode.hget()

