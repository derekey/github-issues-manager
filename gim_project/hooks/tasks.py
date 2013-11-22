from random import randint

from core.tasks.repository import RepositoryJob

from subscriptions.models import SUBSCRIPTION_STATES


class CheckRepositoryEvents(RepositoryJob):
    """
    Every minute, if the hook is not set, check the new events.
    """
    queue_name = 'check-repo-events'

    def run(self, queue):
        """
        Get the last events of the repository to update data and fetch updated
        issues. Return the delay before a new fetch as told by github
        """
        repository = self.object

        if repository.hook_set:
            # now the hook seems set, stop going on the "check-events" mode,
            # we'll run on the "hook" mode
            return

        try:
            gh = self.gh
        except Exception:
            gh = repository.get_gh()

        if not gh:
            # no subscription, stop updating this repository
            return

        return repository.check_events(gh) or 60

    def on_success(self, queue, result):
        """
        Go check events again in the minimal delay given by gtthub
        This delay is passed as the result argument.
        Do not delay a new job if we have no delay: it's because the run
        method told us that there is no need to, because the hook is now set.
        """
        if result is None:
            return

        self.clone(delayed_for=result)


class CheckRepositoryHook(RepositoryJob):
    """
    Every 15 minutes (+-2mn), check if the hook is set and if None and if there
    is no job to fetch events every minute, create one.
    """
    queue_name = 'check-repo-hook'

    def run(self, queue):
        """
        Check if the hook exist for this modele. If not, try to add a job to
        start checking events every minute (if one already exists, no new one
        will be added)
        """
        repository = self.object

        try:
            gh = self.gh
        except Exception:
            gh = repository.get_gh(rights=[SUBSCRIPTION_STATES.ADMIN])

        if gh:
            repository.check_hook(gh)

        if not repository.hook_set:
            # no hook, we need to go on the "check-events" mode
            CheckRepositoryEvents.add_job(repository.pk)

    def on_success(self, queue, result):
        """
        Go check hook again in 15 +- 2mn
        """
        self.clone(delayed_for=60 * 13 + randint(0, 60 * 4))
