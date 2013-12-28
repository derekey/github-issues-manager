from core.tasks.repository import RepositoryJob

from .models import GraphData


class UpdateGraphsData(RepositoryJob):
    queue_name = 'update-graphs-data'

    def run(self, queue):
        graph, _ = GraphData.get_or_connect(repository_id=self.identifier.hget())
        graph.reset_issues_and_prs_by_day()
