
from limpyd import fields

from core.models import Repository

from . import DjangoModelJob, DelayableJob


class RepositoryJob(DjangoModelJob):
    """
    Abstract job model for jobs based on the Repository model
    """
    abstract = True
    model = Repository


class FetchClosedIssuesWithNoClosedBy(DelayableJob, RepositoryJob):
    """
    Job that fetches issues from a repository, that are closed but without a
    closed_by (to get the closer_by, we need to fetch each closed issue
    individually)
    """
    queue_name = 'fetch-closed-issues'

    limit = fields.InstanceHashField()
    count = fields.InstanceHashField()

    def run(self, queue):
        """
        Get the repository and update some closed issues
        """
        super(FetchClosedIssuesWithNoClosedBy, self).run(queue)

        count = self.object.fetch_closed_issues_without_closed_by(
                                limit=int(self.limit.hget() or 20), gh=self.gh)
        return count

    def on_success(self, queue, result):
        """
        Save the count of closed issues fetched
        """
        self.count.hset(result)

    def success_message_addon(self, queue, result):
        """
        Display the count of closed issues fetched
        """
        return ' [fetched=%d]' % result
