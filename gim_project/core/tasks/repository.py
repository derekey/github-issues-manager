__all__ = [
    'FetchClosedIssuesWithNoClosedBy',
    'FetchUpdatedPullRequests',
    'FetchUnmergedPullRequests',
    'FirstFetch',
    'FirstFetchStep2',
    'FetchUnfetchedCommits',
    'FetchForUpdate',
]

from datetime import timedelta
from dateutil.parser import parse
from random import randint

from limpyd import fields
from async_messages import messages

from core.models import Repository, GithubUser
from subscriptions.models import WaitingSubscription, WAITING_SUBSCRIPTION_STATES

from .base import DjangoModelJob, Job


class RepositoryJob(DjangoModelJob):
    """
    Abstract job model for jobs based on the Repository model
    """
    abstract = True
    model = Repository

    @property
    def repository(self):
        if not hasattr(self, '_repository'):
            self._repository = self.object
        return self._repository


class FetchClosedIssuesWithNoClosedBy(RepositoryJob):
    """
    Job that fetches issues from a repository, that are closed but without a
    closed_by (to get the closer_by, we need to fetch each closed issue
    individually)
    """
    queue_name = 'fetch-closed-issues'

    limit = fields.InstanceHashField()
    count = fields.InstanceHashField()
    errors = fields.InstanceHashField()

    permission = 'read'
    clonable_fields = ('gh', 'limit', )

    def run(self, queue):
        """
        Get the repository and update some closed issues, and save the count
        of fetched issues in the job
        """
        super(FetchClosedIssuesWithNoClosedBy, self).run(queue)

        gh = self.gh
        if not gh:
            return  # it's delayed !

        count, deleted, errors, todo = self.repository.fetch_closed_issues_without_closed_by(
                                                    limit=int(self.limit.hget() or 20), gh=gh)

        self.hmset(count=count, errors=errors)

        return count, deleted, errors, todo

    def on_success(self, queue, result):
        """
        If there is still issues to fetch, add a new job
        """
        todo = result[3]
        if todo:
            self.clone(delayed_for=60)

    def success_message_addon(self, queue, result):
        """
        Display the count of closed issues fetched
        """
        return ' [fetched=%d, deleted=%s, errors=%s, todo=%s]' % result


class FetchUpdatedPullRequests(RepositoryJob):
    """
    Job that fetches updated pull requests from a repository, to have infos we
    can only have by fetching them one by one
    """
    queue_name = 'update-pull-requests'

    limit = fields.InstanceHashField()
    count = fields.InstanceHashField()
    errors = fields.InstanceHashField()

    permission = 'read'
    clonable_fields = ('gh', 'limit', )

    def run(self, queue):
        """
        Get the repository and update some pull requests, and save the count
        of updated pull requests in the job
        """
        super(FetchUpdatedPullRequests, self).run(queue)

        gh = self.gh
        if not gh:
            return  # it's delayed !

        count, deleted, errors, todo = self.repository.fetch_updated_prs(
                                    limit=int(self.limit.hget() or 20), gh=gh)

        self.hmset(count=count, errors=errors)

        return count, deleted, errors, todo

    def on_success(self, queue, result):
        """
        If there is still PRs to fetch, add a new job
        """
        todo = result[3]
        if todo:
            self.clone(delayed_for=60)

    def success_message_addon(self, queue, result):
        """
        Display the count of updated pull requests
        """
        return ' [fetched=%d, deleted=%s, errors=%s, todo=%s]' % result


class FetchUnmergedPullRequests(RepositoryJob):
    """
    Job that fetches open pull requests from a repository, to update their
    mergeable status
    """
    queue_name = 'update-mergable-status'

    start_date = fields.InstanceHashField()
    limit = fields.InstanceHashField()
    count = fields.InstanceHashField()
    errors = fields.InstanceHashField()

    permission = 'read'
    clonable_fields = ('gh', 'limit', )

    def run(self, queue):
        """
        Get the repository and update some pull requests, and save the count
        of updated pull requests in the job
        """
        super(FetchUnmergedPullRequests, self).run(queue)

        gh = self.gh
        if not gh:
            return  # it's delayed !

        start_date = self.start_date.hget()
        if start_date:
            start_date = parse(start_date)
        else:
            start_date = None

        count, updated, deleted, errors, todo, last_date = self.repository.fetch_unmerged_prs(
                                limit=int(self.limit.hget() or 20), gh=gh, start_date=start_date)

        self.hmset(count=updated, errors=errors)

        return count, updated, deleted, errors, todo, last_date

    def on_success(self, queue, result):
        """
        If there is still PRs to fetch, add a new job
        """
        todo = result[4]
        if todo:
            last_date = result[5]
            self.clone(priority=-15, delayed_for=60, start_date=str(last_date-timedelta(seconds=1)))

    def success_message_addon(self, queue, result):
        """
        Display the count of updated pull requests
        """
        return ' [fetched=%d, updated=%s, deleted=%s, errors=%s, todo=%s]' % result[:-1]


class FirstFetch(Job):
    """
    A job to do the first fetch of a repository.
    It's a specific job because when the job will be fetched, the waiting
    subscriptions associated with it will be converted to real ones.
    """
    queue_name = 'first-repository-fetch'

    converted_subscriptions = fields.InstanceHashField()

    permission = 'self'

    def run(self, queue):
        """
        Fetch the repository and once done, convert waiting subscriptions into
        real ones, and save the cout of converted subscriptions in the job.
        """
        super(FirstFetch, self).run(queue)

        gh = self.gh
        if not gh:
            return  # it's delayed !

        # the identifier of this job is not the repository's id, but its full name
        repository_name = self.identifier.hget()

        # mark waiting subscriptions as in fetching status
        WaitingSubscription.objects.filter(repository_name=repository_name)\
            .update(state=WAITING_SUBSCRIPTION_STATES.FETCHING)

        # get the user who asked to add this repo, and check its rights
        user = GithubUser.objects.get(username=self.gh_args.hget('username'))
        rights = user.can_use_repository(repository_name)

        # TODO: in these two case, we must not retry the job without getting
        #       an other user with fetch rights
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
        if not repository.first_fetch_done:
            repository.fetch_all(gh=self.gh, force_fetch=True, two_steps=True)

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

        # save count in the job
        self.converted_subscriptions.hset(count)

        # add check-hook/events jobs
        # TODO: should not be in core but for now...
        from hooks.tasks import CheckRepositoryHook, CheckRepositoryEvents
        CheckRepositoryEvents.add_job(repository.id)
        CheckRepositoryHook.add_job(repository.id, delayed_for=30)

        # return the number of converted subscriptions
        return count

    def success_message_addon(self, queue, result):
        """
        Display the count of converted subscriptions
        """
        return ' [converted=%d]' % result


class FirstFetchStep2(RepositoryJob):
    """
    A job to fetch the less important data of a repository (closed issues and
    comments)
    """
    queue_name = 'repository-fetch-step2'
    clonable_fields = ('gh', 'max_pages', )

    start_page = fields.InstanceHashField()
    max_pages = fields.InstanceHashField()
    to_ignore = fields.SetField()

    counts = fields.HashField()
    last_one = fields.InstanceHashField()

    permission = 'read'

    def run(self, queue):
        """
        Call the fetch_all_step2 method of the linked repository, using the
        value of the start_page and max_pages job's attributes
        """
        super(FirstFetchStep2, self).run(queue)

        gh = self.gh
        if not gh:
            return  # it's delayed !

        self._start_page, self._max_pages = self.hmget('start_page', 'max_pages')

        try:
            self._start_page = int(self._start_page)
        except Exception:
            self._start_page = 1
            self.start_page.hset(self._start_page)

        try:
            self._max_pages = int(self._max_pages)
        except Exception:
            self._max_pages = 5
            self.max_pages.hset(self._max_pages)

        try:
            self._to_ignore = set(self.to_ignore.smembers())
        except:
            self._to_ignore = None

        counts = self.repository.fetch_all_step2(gh=gh, force_fetch=True,
                        start_page=self._start_page, max_pages=self._max_pages,
                        to_ignore=self._to_ignore, issues_state='closed')

        return counts

    def on_success(self, queue, result):
        """
        When done, if something was fetched, add a new job to continue the fetch
        of following pages one minute later.
        If nothing was fetched, we are done and add a job to do a new full
        fetch to check updates.
        """

        if result:
            self.counts.hmset(**result)
            total_count = sum(result.values())
        else:
            total_count = 0

        if total_count:
            # we got data, continue at least one time

            self._to_ignore.update([k for k, v in result.iteritems() if not v])

            kwargs = {'start_page': self._start_page + self._max_pages}
            if self._to_ignore:
                kwargs['to_ignore'] = self._to_ignore  # cannot sadd an empty set

            self.clone(delayed_for=60, **kwargs)

        else:
            # got nothing, it's the end, add a job to do future fetches
            self.last_one.hset(1)
            FetchForUpdate.add_job(self.object.id, gh=self.gh)

    def success_message_addon(self, queue, result):
        msg = ' [%s]' % (', '.join(['%s=%s' % (k, v) for k, v in result.iteritems()]))

        if result and sum(result.values()):

            msg += ' - Continue (start page %s for %s pages)' % (
                            self._start_page + self._max_pages, self._max_pages)

        else:
            msg += ' - The end.'

        return msg


class FetchUnfetchedCommits(RepositoryJob):
    """
    Job that fetches commit objects that weren't be fetched, for example just
    created with a sha.
    """
    queue_name = 'fetch-unfetched-commits'

    limit = fields.InstanceHashField()
    count = fields.InstanceHashField()
    errors = fields.InstanceHashField()
    deleted = fields.InstanceHashField()

    permission = 'read'
    clonable_fields = ('gh', 'limit', )

    def run(self, queue):
        """
        Get the repository and fetch unfetched commits, and save the count
        of fetched comits in the job
        """
        super(FetchUnfetchedCommits, self).run(queue)

        gh = self.gh
        if not gh:
            return  # it's delayed !

        count, deleted, errors, todo = self.repository.fetch_unfetched_commits(
                                    limit=int(self.limit.hget() or 20), gh=gh)

        self.hmset(count=count, errors=errors, deleted=deleted)

        return count, deleted, errors, todo

    def on_success(self, queue, result):
        """
        If there is still commits to fetch, add a new job
        """
        todo = result[3]
        if todo:
            self.clone(delayed_for=60)

    def success_message_addon(self, queue, result):
        """
        Display the count of fetched commits
        """
        return ' [fetched=%d, deleted=%s, errors=%s, todo=%s]' % result


class FetchForUpdate(RepositoryJob):
    """
    Job that will do an unforced full fetch of the repository to update all that
    needs to.
    When done, clone the job to be done again 15 min laters (+-2mn)
    """
    queue_name = 'update-repo'

    permission = 'read'
    clonable_fields = ('gh', )

    def run(self, queue):
        """
        Fetch the whole repository stuff if it has a subscription
        """
        super(FetchForUpdate, self).run(queue)

        gh = self.gh
        if not gh:
            return  # it's delayed !

        self.repository.fetch_all(gh)

    def on_success(self, queue, result):
        """
        Go fetch again in 15 +- 2mn
        """
        self.clone(delayed_for=60 * 13 + randint(0, 60 * 4))
