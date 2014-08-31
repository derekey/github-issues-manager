__all__ = [
    'UpdateGraphsData',
]

from gim.core.tasks.repository import RepositoryJob


class UpdateGraphsData(RepositoryJob):
    queue_name = 'update-graphs-data'

    def run(self, queue):
        from .limpyd_models import GraphData
        graph, _ = GraphData.get_or_connect(repository_id=self.identifier.hget())
        graph.reset_issues_and_prs_by_day()
