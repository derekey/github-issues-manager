
from limpyd import fields

from core.models import GithubUser

from . import LimpydJob, DjangoModelJob


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
    queue_name = 'fetch-avaiable-repos'

    nb_repos = fields.InstanceHashField()
    nb_orgs = fields.InstanceHashField()

    def run(self, queue):
        """
        Get the user and its available repositories from github
        """
        super(FetchAvailableRepositoriesJob, self).run(queue)

        result = self.object.fetch_available_repositories()

        return result

    def on_success(self, queue, result):
        """
        Save infos got from the fetch_available_repositories call
        """
        nb_repos, nb_orgs = result
        self.hmset(nb_repos=nb_repos, nb_orgs=nb_orgs)

    def success_message_addon(self, queue, result):
        """
        Display infos got from the fetch_available_repositories call
        """
        nb_repos, nb_orgs = result
        return ' [nb_repos=%d, nb_orgs=%d]' % (nb_repos, nb_orgs)
