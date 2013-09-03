
from limpyd import fields
from async_messages import messages

from core.models import Repository, GithubUser
from subscriptions.models import WaitingSubscription, WAITING_SUBSCRIPTION_STATES

from . import DjangoModelJob, DelayableJob, Job


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


class FirstFetch(Job):
    """
    A job to do the first fetch of a repository.
    It's a specific job because when the job will be fetched, the waiting
    subscriptions associated with it will be converted to real ones.
    """
    queue_name = 'first-repository-fetch'

    converted_subscriptions = fields.InstanceHashField()

    def run(self, queue):
        """
        Fetch the repository and once done, convert waiting subscriptions into
        real ones
        """
        super(FirstFetch, self).run(queue)

        # the identifier of this job is not the repository's id, but its full name
        repository_name = self.identifier.hget()

        # mark waiting subscriptions as in fetching status
        WaitingSubscription.objects.filter(repository_name=repository_name)\
            .update(state=WAITING_SUBSCRIPTION_STATES.FETCHING)

        # get the user who asked to add this repo, and check its rights
        user = GithubUser.objects.get(username=self.gh_args.hget('username'))
        rights = user.can_use_repository(repository_name)

        if rights is None:
            raise Exception('An error occured while fetching rights for the user')
        elif rights is False:
            raise Exception('The user has not rights to fetch this repository')

        # try to get a GithubUser which is the owner of the repository
        user_part, repo_name_part = repository_name.split('/')

        if user_part == user.username:
            owner = user
        else:
            try:
                owner = GithubUser.objects.get(username=user_part)
            except GithubUser.DoesNotExist:
                # no user, we will create it during the fetch
                owner = GithubUser(username=user_part)

        # Check if the repository already exists in the DB
        repository = None
        if owner.id:
            try:
                repository = owner.owned_repositories.get(name=repo_name_part)
            except Repository.DoesNotExist:
                pass

        if not repository:
            # create a temporary repository to fetch if none exists
            repository = Repository(name=repo_name_part, owner=owner)

        # fetch the repository if never fetched
        if not repository.fetched_at:
            repository.fetch_all(gh=self.gh)

        # and convert waiting subscriptions to real ones
        count = 0
        for subscription in WaitingSubscription.objects.filter(repository_name=repository_name):
            try:
                rights = subscription.user.can_use_repository(repository)
            except Exception:
                continue
            if rights:
                count += 1
                subscription.convert(rights)
                message = u'Your subscription to <strong>%s</strong> is now ready' % repository.full_name
                messages.success(subscription.user, message)
            else:
                subscription.state = WAITING_SUBSCRIPTION_STATES.FAILED
                subscription.save(update_fields=('state', ))

        # return the number of converted subscriptions
        return count

    def on_success(self, queue, result):
        """
        Save the count of converted subscriptions
        """
        self.converted_subscriptions.hset(result)

    def success_message_addon(self, queue, result):
        """
        Display the count of converted subscriptions
        """
        return ' [converted=%d]' % result
