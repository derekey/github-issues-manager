__all__ = [
    'FetchAvailableRepositoriesJob',
]

from limpyd import fields
from async_messages import messages

from core.models import GithubUser

from .base import DjangoModelJob


class UserJob(DjangoModelJob):
    """
    Abstract job model for jobs based on the GithubUser model
    """
    abstract = True
    model = GithubUser


class FetchAvailableRepositoriesJob(UserJob):
    """
    Job that fetches available repositories of a user
    """
    queue_name = 'fetch-available-repos'

    nb_repos = fields.InstanceHashField()
    nb_orgs = fields.InstanceHashField()

    def run(self, queue):
        """
        Get the user and its available repositories from github, and save the
        counts in the job
        """
        super(FetchAvailableRepositoriesJob, self).run(queue)

        user = self.object

        nb_repos, nb_orgs = user.fetch_available_repositories()

        message = u'The list of repositories you can subscribe to was just updated'
        messages.success(user, message)

        self.hmset(nb_repos=nb_repos, nb_orgs=nb_orgs)

        return nb_repos, nb_orgs

    def success_message_addon(self, queue, result):
        """
        Display infos got from the fetch_available_repositories call
        """
        nb_repos, nb_orgs = result
        return ' [nb_repos=%d, nb_orgs=%d]' % (nb_repos, nb_orgs)
