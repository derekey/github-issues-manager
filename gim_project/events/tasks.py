__all__ = [
    'ResetRepositoryCounters',
]
from core.tasks.repository import RepositoryJob


class ResetRepositoryCounters(RepositoryJob):
    queue_name = 'reset-repo-counters'

    def run(self, queue):
        counters = self.object.counters
        counters.update_global()
        counters.update_users()
