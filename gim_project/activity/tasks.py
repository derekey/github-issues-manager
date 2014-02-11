__all__ = [
    'ResetIssueActivity',
]

from core.tasks.issue import IssueJob


class ResetIssueActivity(IssueJob):
    queue_name = 'reset-issue-activity'

    def run(self, queue):
        try:
            self.object.activity.update()
        except self.model.DoesNotExist:
            # self.status.hset(STATUSES.CANCELED)
            return False
