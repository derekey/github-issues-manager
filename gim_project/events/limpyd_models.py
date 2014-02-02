from collections import Counter
from itertools import product

from limpyd import model as lmodel, fields as lfields

from core import get_main_limpyd_database
from core.models import Repository


class RepositoryCounters(lmodel.RedisModel):

    database = get_main_limpyd_database()

    repository_id = lfields.InstanceHashField(indexable=True)

    # total count of issues and prs
    total = lfields.InstanceHashField()
    # total count of issues (not prs)
    issues = lfields.InstanceHashField()
    # total count of prs
    prs = lfields.InstanceHashField()

    # total count of open issues and prs
    open_total = lfields.InstanceHashField()
    # total count of open issues (not prs)
    open_issues = lfields.InstanceHashField()
    # total count of open prs
    open_prs = lfields.InstanceHashField()

    # count of assigned open issues and prs for users
    assigned_total_for = lfields.HashField()
    # count of assigned open issues (not prs) for users
    assigned_issues_for = lfields.HashField()
    # count of assigned open prs for users
    assigned_prs_for = lfields.HashField()

    # count of created open issues and prs for users
    created_total_for = lfields.HashField()
    # count of created open issues (not prs) for users
    created_issues_for = lfields.HashField()
    # count of created open prs for users
    created_prs_for = lfields.HashField()

    @property
    def repository(self):
        if not hasattr(self, '_repository'):
            self._repository = Repository.objects.get(pk=self.repository_id.hget())
        return self._repository

    def get_global_counts(self):
        counts = self.hmget(
            'total', 'issues', 'prs',
            'open_total', 'open_issues', 'open_prs',
        )

        return {
            'total': {
                'total': int(counts[0] or 0),
                'issues': int(counts[1] or 0),
                'prs': int(counts[2] or 0),
            },
            'open': {
                'total': int(counts[3] or 0),
                'issues': int(counts[4] or 0),
                'prs': int(counts[5] or 0),
            }
        }

    def get_user_counts(self, user_pk):
        with self.database.pipeline(transaction=False) as pipeline:
            for typ, limit in product(('assigned', 'created'), ('total', 'issues', 'prs')):
                getattr(self, '%s_%s_for' % (typ, limit)).hget(user_pk)
            counts = pipeline.execute()

        return {
            'assigned': {
                'total': int(counts[0] or 0),
                'issues': int(counts[1] or 0),
                'prs': int(counts[2] or 0),
            },
            'created': {
                'total': int(counts[3] or 0),
                'issues': int(counts[4] or 0),
                'prs': int(counts[5] or 0),
            }
        }

    def update_global(self):
        qs = self.repository.issues

        counts = {
            'total': qs.count(),
            'issues': 0,
            'prs': 0,
            'open_total': 0,
            'open_issues': 0,
            'open_prs': 0,
        }

        if counts['total']:
            counts['issues'] = qs.filter(is_pull_request=False).count()
            counts['prs'] = counts['total'] - counts['issues']

            qs = qs.filter(state='open')
            counts['open_total'] = qs.count()
            if counts['open_total']:
                if counts['issues']:
                    counts['open_issues'] = qs.filter(is_pull_request=False).count()
                counts['open_prs'] = counts['open_total'] - counts['open_issues']

        self.hmset(**counts)

    def update_user(self, user_pk):
        qs = self.repository.issues.filter(state='open')
        qs_a = qs.filter(assignee=user_pk)
        qs_c = qs.filter(user=user_pk)

        counts = {
            'assigned_total': qs_a.count(),
            'assigned_issues': 0,
            'assigned_prs': 0,
            'created_total': qs_c.count(),
            'created_issues': 0,
            'created_prs': 0,
        }

        if counts['assigned_total']:
            counts['assigned_issues'] = qs_a.filter(is_pull_request=False).count()
            counts['assigned_prs'] = counts['assigned_total'] - counts['assigned_issues']

        if counts['created_total']:
            counts['created_issues'] = qs_c.filter(is_pull_request=False).count()
            counts['created_prs'] = counts['created_total'] - counts['created_issues']

        with self.database.pipeline(transaction=False) as pipeline:
            for field, value in counts.items():
                getattr(self, '%s_for' % field).hset(user_pk, value)
            pipeline.execute()

    def update_users(self):
        qs = self.repository.issues.filter(state='open')
        qs_limit = {
            'issues': qs.filter(is_pull_request=False),
            'prs': qs.filter(is_pull_request=True),
        }

        counters = {}
        for typ, field in (('assigned', 'assignee'), ('created', 'user')):
            counters[typ] = {
                'total': Counter(map(str, qs.values_list(field, flat=True))) or {},
                'issues': {},
                'prs': {},
            }
            if counters[typ]['total']:
                for limit in ('issues', 'prs'):
                    counters[typ][limit] = Counter(map(str, qs_limit[limit].values_list(field, flat=True))) or {}

        with self.database.pipeline(transaction=False) as pipeline:
            for typ, limit in product(('assigned', 'created'), ('total', 'issues', 'prs')):
                field = getattr(self, '%s_%s_for' % (typ, limit))
                field.delete()
                if counters[typ][limit]:
                    field.hmset(**counters[typ][limit])

            pipeline.execute()

    def update_from_created_issue(self, issue):
        with self.database.pipeline(transaction=False) as pipeline:

            limit = 'prs' if issue.is_pull_request else 'issues'

            self.total.hincrby(1)
            getattr(self, limit).hincrby(1)

            if issue.state == 'open':
                self.open_total.hincrby(1)
                getattr(self, 'open_%s' % limit).hincrby(1)

                self.created_total_for.hincrby(issue.user_id, 1)
                getattr(self, 'created_%s_for' % limit).hincrby(issue.user_id, 1)

                if issue.assignee_id:
                    self.assigned_total_for.hincrby(issue.assignee_id, 1)
                    getattr(self, 'assigned_%s_for' % limit).hincrby(issue.assignee_id, 11)

            pipeline.execute()

        self.repository.ask_for_counters_update()

    def update_from_updated_issue(self, issue, changed_fields):
        # if new state is close: decrease old assignee/created and global open
        # if new state is open: increase new assignee/created and global open
        # if unchanged state is open: decrease old assignee, increase new one
        # if unchanged state is close: do nothing

        # if unchanged state is close: no nothing
        if 'state' not in changed_fields and issue.state == 'close':
            return

        updates = {}

        # if unchanged state is open: decrease old assignee, increase new one
        if 'state' not in changed_fields:
            if 'assignee_id' not in changed_fields:
                # assignee unchanged, nothing to do
                return
            else:
                # decrease old assignee
                updates['old-assignee'] = -1
                # increase new assignee
                updates['new-assignee'] = 1

        else:
            # if here, new state has changed
            if issue.state == 'close':
                # decreatese old assignee
                updates['old-assignee'] = -1
                # decrease created
                updates['created'] = -1
                # decrease global open
                updates['all'] = -1
            else:
                # increase new assignee
                updates['new-assignee'] = 1
                # increase new created
                updates['created'] = 1
                # increase global open
                updates['all'] = 1

        if not updates:
            return

        limit = 'prs' if issue.is_pull_request else 'issues'

        with self.database.pipeline(transaction=False) as pipeline:
            if 'all' in updates:
                self.open_total.hincrby(updates['all'])
                getattr(self, 'open_%s' % limit).hincrby(updates['all'])

            if 'old-assignee' in updates:
                assignee_id = changed_fields.get('assignee_id', issue.assignee_id)
                self.assigned_total_for.hincrby(assignee_id, updates['old-assignee'])
                getattr(self, 'assigned_%s_for' % limit).hincrby(assignee_id, updates['old-assignee'])

            if 'new-assignee' in updates:
                self.assigned_total_for.hincrby(issue.assignee_id, updates['new-assignee'])
                getattr(self, 'assigned_%s_for' % limit).hincrby(issue.assignee_id, updates['new-assignee'])

            if 'created' in updates:
                self.created_total_for.hincrby(issue.user_id, updates['created'])
                getattr(self, 'created_%s_for' % limit).hincrby(issue.user_id, updates['created'])

            pipeline.execute()

        self.repository.ask_for_counters_update()
