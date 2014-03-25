__all__ = [
    'SearchReferenceCommit',
]

from limpyd import fields
from limpyd_jobs import STATUSES
from limpyd_jobs.utils import compute_delayed_until

from core.models import IssueEvent, Commit

from .base import DjangoModelJob


class EventJob(DjangoModelJob):
    """
    Abstract job model for jobs based on the Event model
    """
    abstract = True
    model = IssueEvent

    @property
    def event(self):
        if not hasattr(self, '_event'):
            self._event = self.object
        return self._event

    @property
    def repository(self):
        if not hasattr(self, '_repository'):
            self._repository = self.event.repository
        return self._repository


class SearchReferenceCommit(EventJob):
    """
    When an event is a reference to a commit, we may not have it, so we'll
    wait because it may have been fetched after the event was received
    """
    queue_name = 'search-ref-commit'

    nb_tries = fields.InstanceHashField()

    def run(self, queue):
        super(SearchReferenceCommit, self).run(queue)

        event = self.event

        try:
            # try to find the matching commit
            event.related_object = Commit.objects.get(
                authored_at=event.created_at,
                sha=event.commit_sha,
                author=event.user
            )
        except Commit.DoesNotExist:
            # the commit was not found

            tries = int(self.nb_tries.hget() or 0)

            if tries >= 5:
                # enough tries, stop now
                self.status.hset(STATUSES.CANCELED)
                return None
            else:
                # we'll try again...
                self.status.hset(STATUSES.DELAYED)
                self.delayed_until.hset(compute_delayed_until(delayed_for=60*(tries+1)))
                self.nb_tries.hincrby(1)
            return False

        # commit found, save the event
        event.save()

        return True
