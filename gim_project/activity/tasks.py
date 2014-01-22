from core.tasks.issue import IssueJob


class ResetIssueActivity(IssueJob):
    queue_name = 'reset-issue-activity'

    def run(self, queue):
        self.object.activity.update()
