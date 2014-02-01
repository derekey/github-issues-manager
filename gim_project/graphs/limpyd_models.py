from collections import defaultdict
from datetime import datetime, timedelta
from dateutil.parser import parse

from limpyd import model as lmodel, fields as lfields

from core import get_main_limpyd_database
from core.models import Repository


class GraphData(lmodel.RedisModel):

    database = get_main_limpyd_database()

    repository_id = lfields.InstanceHashField(indexable=True)

    issues_by_day = lfields.SortedSetField()

    @property
    def repository(self):
        if not hasattr(self, '_repository'):
            self._repository = Repository.objects.get(id=self.repository_id.hget())
        return self._repository

    def reset_issues_and_prs_by_day(self):
        today = datetime.utcnow()

        nb_issues = defaultdict(int)
        nb_prs = defaultdict(int)

        issues = list(self.repository.issues.values(
                        'created_at', 'closed_at', 'state', 'is_pull_request'
                    ).order_by('created_at'))

        if len(issues):
            min_date = issues[0]['created_at'].date()

            # save counts
            for issue in issues:
                start = issue['created_at'].date()
                end = (issue['closed_at'] or today).date()
                closed = issue['state'] == 'closed'
                for d in [0] + range(1, (end - start).days + (0 if closed else 1)):
                    counter = nb_prs if issue['is_pull_request'] else nb_issues
                    key = str(start + timedelta(days=d))
                    counter[key] += 1

            # prepare zset
            z_issues = {}
            for d in xrange((today.date() - min_date).days + 1):
                key = str(min_date + timedelta(days=d))
                score = int(key.replace('-', ''))
                value = '%s:%d:%d' % (score, nb_issues.get(key, 0), nb_prs.get(key, 0))
                z_issues[value] = score

            # delete and save in one pass
            with self.database.pipeline() as pipeline:
                self.issues_by_day.delete()

                self.issues_by_day.zadd(**z_issues)

                pipeline.execute()

    def get_issues_and_prs_by_day(self, duration=365, include_dates=True):
        today = datetime.utcnow().date()
        start = today - timedelta(days=duration - 1)
        min_score = int(str(start).replace('-', ''))
        max_score = int(str(today).replace('-', ''))

        data = self.issues_by_day.zrangebyscore(min_score, max_score)
        if len(data):
            splitted_data = [x.split(':') for x in data]

            if include_dates:
                result = [(parse(d).date(), int(i), int(p)) for d, i, p in splitted_data]
            else:
                result = [(int(i), int(p)) for d, i, p in splitted_data]

            max_value = max([r[-1] + r[-2] for r in result])
        else:
            max_value = 0
            result = []

        return {
            'max': max_value,
            'data': result,
        }
