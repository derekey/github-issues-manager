__all__ = [
    'CheckRepositoryEvents',
    'CheckRepositoryHook',
]

from random import randint

from limpyd_jobs import STATUSES

from gim.core.tasks.repository import RepositoryJob


class CheckRepositoryEvents(RepositoryJob):
    """
    Every minute, if the hook is not set, check the new events.
    """
    queue_name = 'check-repo-events'

    permission = 'read'

    def run(self, queue):
        """
        Get the last events of the repository to update data and fetch updated
        issues. Return the delay before a new fetch as told by github
        """
        repository = self.object

        if repository.hook_set or not repository.has_subscriptions():
            # now the hook seems set, stop going on the "check-events" mode,
            # we'll run on the "hook" mode
            # also, do not fetch events if no sbuscriptions for a repository
            self.status.hset(STATUSES.CANCELED)
            return

        gh = self.gh
        if not gh:
            return  # it's delayed !

        updated_issues_count, delay = repository.check_events(gh)

        return updated_issues_count, delay or 60

    def on_success(self, queue, result):
        """
        Go check events again in the minimal delay given by gtthub, but only if
        the hook is not set on this repository
        This delay is passed as the result argument.
        """
        updated_issues_count, delay = result
        self.clone(delayed_for=delay + randint(0, 10))

    def success_message_addon(self, queue, result):
        """
        Display the count of updated issues
        """
        updated_issues_count, delay = result
        return ' [updated=%d]' % updated_issues_count


class CheckRepositoryHook(RepositoryJob):
    """
    Every 15 minutes (+-2mn), check if the hook is set and if None and if there
    is no job to fetch events every minute, create one.
    """
    queue_name = 'check-repo-hook'

    permission = 'admin'

    def run(self, queue):
        """
        Check if the hook exist for this modele. If not, try to add a job to
        start checking events every minute (if one already exists, no new one
        will be added)
        """
        repository = self.object

        gh = self.gh
        if not gh:
            return  # it's delayed !

        repository.check_hook(gh)

        return repository.hook_set

    def on_success(self, queue, result):
        """
        If the repository hook is not set, add a job to fetch events, and check
        the hook again in 15 +- 2mn
        """
        if not result:
            # no hook, we need to go on the "check-events" mode
            CheckRepositoryEvents.add_job(self.identifier.hget())
        else:
            # we have a hook, stop checking events
            for j in CheckRepositoryEvents.collection(
                        queued=1, identifier=self.identifier.hget()).instances():
                j.status.hset(STATUSES.CANCELED)

        self.clone(delayed_for=60 * 13 + randint(0, 60 * 4))
