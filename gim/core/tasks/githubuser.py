__all__ = [
    'FetchAvailableRepositoriesJob',
]

from limpyd import fields
from async_messages import messages

from gim.core.models import GithubUser

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

    inform_user = fields.InstanceHashField()

    clonable_fields = ('gh', )
    permission = 'self'

    def run(self, queue):
        """
        Get the user and its available repositories from github, and save the
        counts in the job
        """
        super(FetchAvailableRepositoriesJob, self).run(queue)

        user = self.object

        # force gh if not set
        if not self.gh_args.hgetall():
            gh = user.get_connection()
            if gh and 'access_token' in gh._connection_args:
                self.gh = gh

        # check availability
        gh = self.gh
        if not gh:
            return  # it's delayed !

        nb_repos, nb_orgs, nb_watched, nb_starred, nb_teams = user.fetch_all()

        if self.inform_user.hget() == '1':
            if nb_repos + nb_teams:
                message = u'The list of repositories you can subscribe to (ones you own, collaborate to, or in your organizations) was just updated'
            else:
                message = u'There is no new repositories you own, collaborate to, or in your organizations'
            messages.success(user, message)

        upgraded, downgraded = user.check_subscriptions()

        return nb_repos, nb_orgs, nb_watched, nb_starred, nb_teams, len(upgraded), len(downgraded)

    def success_message_addon(self, queue, result):
        """
        Display infos got from the fetch_available_repositories call
        """
        nb_repos, nb_orgs, nb_watched, nb_starred, nb_teams, nb_upgraded, nb_downgraded = result
        return ' [nb_repos=%d, nb_orgs=%d, nb_watched=%d, nb_starred=%d, nb_teams=%d, nb_upgraded=%d, nb_downgraded=%d]' % (
                nb_repos, nb_orgs, nb_watched, nb_starred, nb_teams, nb_upgraded, nb_downgraded)

    def on_success(self, queue, result):
        """
        Make a new fetch later
        """
        self.clone(delayed_for=60*60*3)  # once per 3h
