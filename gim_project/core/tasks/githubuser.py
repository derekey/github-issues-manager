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
    nb_teams = fields.InstanceHashField()

    def run(self, queue):
        """
        Get the user and its available repositories from github, and save the
        counts in the job
        """
        super(FetchAvailableRepositoriesJob, self).run(queue)

        user = self.object

        gh = user.get_connection()
        nb_repos, nb_teams = user.fetch_all(gh)

        if nb_repos + nb_teams:
            message = u'The list of repositories you can subscribe to (ones you own, collaborate to, or in your organisations) was just updated'
        else:
            message = u'There is no new repositories you own, collaborate to, or in your organizations'
        messages.success(user, message)

        self.hmset(nb_repos=nb_repos, nb_teams=nb_teams)

        return nb_repos, nb_teams

    def success_message_addon(self, queue, result):
        """
        Display infos got from the fetch_available_repositories call
        """
        nb_repos, nb_teams = result
        return ' [nb_repos=%d, nb_teams=%d]' % (nb_repos, nb_teams)
