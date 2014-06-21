__all__ = [
    'Repository',
]

from datetime import datetime, timedelta

from django.db import models

from .. import GITHUB_HOST

from ..ghpool import (
    ApiError,
    ApiNotFoundError,
)

from ..managers import (
    MODE_ALL,
    MODE_UPDATE,
    RepositoryManager,
)

from .base import (
    GithubObjectWithId,
)


class Repository(GithubObjectWithId):
    owner = models.ForeignKey('GithubUser', related_name='owned_repositories')
    name = models.TextField(db_index=True)
    description = models.TextField(blank=True, null=True)
    collaborators = models.ManyToManyField('GithubUser', related_name='repositories')
    private = models.BooleanField(default=False)
    is_fork = models.BooleanField(default=False)
    has_issues = models.BooleanField(default=False)
    default_branch = models.TextField(blank=True, null=True)

    first_fetch_done = models.BooleanField(default=False)
    collaborators_fetched_at = models.DateTimeField(blank=True, null=True)
    collaborators_etag = models.CharField(max_length=64, blank=True, null=True)
    milestones_fetched_at = models.DateTimeField(blank=True, null=True)
    milestones_state_open_etag = models.CharField(max_length=64, blank=True, null=True)
    milestones_state_closed_etag = models.CharField(max_length=64, blank=True, null=True)
    labels_fetched_at = models.DateTimeField(blank=True, null=True)
    labels_etag = models.CharField(max_length=64, blank=True, null=True)
    issues_fetched_at = models.DateTimeField(blank=True, null=True)
    issues_state_open_etag = models.CharField(max_length=64, blank=True, null=True)
    issues_state_closed_etag = models.CharField(max_length=64, blank=True, null=True)
    issues_state_all_etag = models.CharField(max_length=64, blank=True, null=True)
    prs_fetched_at = models.DateTimeField(blank=True, null=True)
    prs_state_open_etag = models.CharField(max_length=64, blank=True, null=True)
    prs_state_closed_etag = models.CharField(max_length=64, blank=True, null=True)
    prs_state_all_etag = models.CharField(max_length=64, blank=True, null=True)
    comments_fetched_at = models.DateTimeField(blank=True, null=True)
    comments_etag = models.CharField(max_length=64, blank=True, null=True)
    pr_comments_fetched_at = models.DateTimeField(blank=True, null=True)
    pr_comments_etag = models.CharField(max_length=64, blank=True, null=True)
    issues_events_fetched_at = models.DateTimeField(blank=True, null=True)
    issues_events_etag = models.CharField(max_length=64, blank=True, null=True)
    commit_comments_fetched_at = models.DateTimeField(blank=True, null=True)
    commit_comments_etag = models.CharField(max_length=64, blank=True, null=True)
    # this list is not ordered, we must memorize the last page
    commit_comments_last_page = models.PositiveIntegerField(blank=True, null=True)

    objects = RepositoryManager()

    github_matching = dict(GithubObjectWithId.github_matching)
    github_matching.update({
        'fork': 'is_fork',
    })
    github_ignore = GithubObjectWithId.github_ignore + ('is_fork', ) + ('issues_url', 'has_wiki',
        'forks_url', 'mirror_url', 'subscription_url', 'notifications_url', 'subscribers_count',
        'updated_at', 'svn_url', 'pulls_url', 'full_name', 'issue_comment_url', 'contents_url',
        'keys_url', 'size', 'tags_url', 'contributors_url', 'network_count', 'downloads_url',
        'assignees_url', 'statuses_url', 'git_refs_url', 'git_commits_url', 'clone_url',
        'watchers_count', 'git_tags_url', 'milestones_url', 'stargazers_count', 'hooks_url',
        'homepage', 'commits_url', 'releases_url', 'issue_events_url', 'has_downloads', 'labels_url',
        'events_url', 'comments_url', 'html_url', 'compare_url', 'open_issues', 'watchers',
        'git_url', 'forks_count', 'merges_url', 'ssh_url', 'blobs_url', 'master_branch', 'forks',
        'permissions', 'open_issues_count', 'languages_url', 'language', 'collaborators_url', 'url',
        'created_at', 'archive_url', 'pushed_at', 'teams_url', 'trees_url',
        'branches_url', 'subscribers_url', 'stargazers_url', )

    class Meta:
        app_label = 'core'
        unique_together = (
            ('owner', 'name'),
        )
        ordering = ('owner', 'name', )

    def __unicode__(self):
        return self.full_name

    @property
    def full_name(self):
        return u'%s/%s' % (self.owner.username if self.owner else '?', self.name)

    @property
    def github_url(self):
        return GITHUB_HOST + self.full_name

    @property
    def untyped_labels(self):
        """
        Shortcut to return a queryset for untyped labels of the repository
        """
        return self.labels.ready().filter(label_type_id__isnull=True)

    def _distinct_users(self, relation):
        from .users import GithubUser
        return GithubUser.objects.filter(**{
                '%s__repository' % relation: self.id
            }).distinct()  # distinct can take the 'username' arg in postgresql

    @property
    def issues_creators(self):
        """
        Shortcut to return a queryset for creator of issues on this repository
        """
        return self._distinct_users('created_issues')

    @property
    def issues_assigned(self):
        """
        Shortcut to return a queryset for users assigned to issues on this repository
        """
        return self._distinct_users('assigned_issues')

    @property
    def issues_closers(self):
        """
        Shortcut to return a queryset for users who closed issues on this repository
        """
        return self._distinct_users('closed_issues')

    @property
    def github_callable_identifiers(self):
        return [
            'repos',
            self.owner.username,
            self.name,
        ]

    @property
    def github_callable_identifiers_for_collaborators(self):
        return self.github_callable_identifiers + [
            'collaborators',
        ]

    def fetch_collaborators(self, gh, force_fetch=False, parameters=None):
        return self._fetch_many('collaborators', gh,
                                force_fetch=force_fetch,
                                parameters=parameters)

    @property
    def github_callable_identifiers_for_labels(self):
        return self.github_callable_identifiers + [
            'labels',
        ]

    def fetch_labels(self, gh, force_fetch=False, parameters=None):
        return self._fetch_many('labels', gh,
                                defaults={
                                    'fk': {'repository': self},
                                    'related': {'*': {'fk': {'repository': self}}},
                                },
                                force_fetch=force_fetch,
                                parameters=parameters)

    @property
    def github_callable_identifiers_for_milestones(self):
        return self.github_callable_identifiers + [
            'milestones',
        ]

    def fetch_milestones(self, gh, force_fetch=False, parameters=None):
        if not self.has_issues:
            return 0
        return self._fetch_many('milestones', gh,
                                vary={'state': ('open', 'closed')},
                                defaults={
                                    'fk': {'repository': self},
                                    'related': {'*': {'fk': {'repository': self}}},
                                },
                                force_fetch=force_fetch,
                                parameters=parameters)

    @property
    def github_callable_identifiers_for_issues(self):
        return self.github_callable_identifiers + [
            'issues',
        ]

    @property
    def github_callable_identifiers_for_prs(self):
        return self.github_callable_identifiers + [
            'pulls',
        ]

    def fetch_issues(self, gh, force_fetch=False, state=None, parameters=None,
                                        parameters_prs=None, max_pages=None):
        from .issues import Issue

        if state:
            vary = {'state': (state, )}
            remove_missing = False
        else:
            vary = {'state': ('all', )}
            remove_missing = True

        count = 0
        if self.has_issues:

            final_issues_parameters = {
                'sort': Issue.github_date_field[1],
                'direction': Issue.github_date_field[2],
            }
            if parameters:
                final_issues_parameters.update(parameters)

            count = self._fetch_many('issues', gh,
                                    vary=vary,
                                    defaults={
                                        'fk': {'repository': self},
                                        'related': {'*': {'fk': {'repository': self}}},
                                    },
                                    parameters=final_issues_parameters,
                                    remove_missing=remove_missing,
                                    force_fetch=force_fetch,
                                    max_pages=max_pages)

        # now fetch pull requests to have more informations for them (only
        # ones that already exist as an issue, not the new ones)

        final_prs_parameters = {
            'sort': Issue.github_date_field[1],
            'direction': Issue.github_date_field[2],
        }
        if parameters_prs:
            final_prs_parameters.update(parameters_prs)

        pr_count = self._fetch_many('issues', gh,
                        vary=vary,
                        defaults={
                            'fk': {'repository': self},
                            'related': {'*': {'fk': {'repository': self}}},
                            'simple': {'is_pull_request': True},
                            'mergeable_state': 'checking',
                        },
                        parameters=final_prs_parameters,
                        remove_missing=False,
                        force_fetch=force_fetch,
                        meta_base_name='prs',
                        modes=MODE_UPDATE if self.has_issues else MODE_ALL,
                        max_pages=max_pages)

        count += pr_count

        if self.has_issues and (not state or state == 'closed'):
            from ..tasks.repository import FetchClosedIssuesWithNoClosedBy
            FetchClosedIssuesWithNoClosedBy.add_job(self.id, limit=20, gh=gh)

        from ..tasks.repository import FetchUpdatedPullRequests
        FetchUpdatedPullRequests.add_job(self.id, limit=20, gh=gh)

        return count

    def fetch_closed_issues_without_closed_by(self, gh, limit=20):
        # the "closed_by" attribute of an issue is not filled in list call, so
        # we fetch all closed issue that has no closed_by, one by one (but only
        # if we never did it because some times there is noone who closed an
        # issue on the github api :( ))
        if not self.has_issues:
            return 0, 0, 0, 0

        qs = self.issues.filter(state='closed',
                                closed_by_id__isnull=True,
                                closed_by_fetched=False
                               )

        issues = list(qs.order_by('-closed_at')[:limit])

        count = errors = deleted = todo = 0

        if len(issues):

            for issue in issues:
                try:
                    issue.fetch(gh, force_fetch=True,
                                defaults={'simple': {'closed_by_fetched': True}})
                except ApiNotFoundError:
                    # the issue doen't exist anymore !
                    issue.delete()
                    deleted += 1
                except ApiError:
                    errors += 1
                else:
                    count += 1

            todo = qs.count()

        return count, deleted, errors, todo

    def fetch_updated_prs(self, gh, limit=20):
        """
        Fetch pull requests individually when it was never done or when the
        updated_at retrieved from the issues list is newer than the previous
        'pr_fetched_at'.
        """
        from .issues import Issue

        filter = self.issues.filter(
            # only pull requests
            models.Q(is_pull_request=True)
            &
            (
                # that where never fetched
                models.Q(pr_fetched_at__isnull=True)
                |
                # or last fetched long time ago
                models.Q(pr_fetched_at__lt=models.F('updated_at'))
                |
                (
                    # or open ones...
                    models.Q(state='open')
                    &
                    (
                        # that are not merged or with unknown merged status
                        models.Q(merged=False)
                        |
                        models.Q(merged__isnull=True)
                    )
                    &
                    (
                        # with unknown mergeable status
                        models.Q(mergeable_state__in=Issue.MERGEABLE_STATES['unknown'])
                        |
                        models.Q(mergeable_state__isnull=True)
                        |
                        models.Q(mergeable__isnull=True)
                    )
                )
                |
                # or closed ones without merged status
                models.Q(merged__isnull=True, state='closed')
            )
        )

        def action(gh, pr):
            pr.fetch_pr(gh, force_fetch=True)
            pr.fetch_commits(gh)
            pr.fetch_files(gh)

        return self._fetch_some_prs(filter, action, gh=gh, limit=limit)

    def fetch_unmerged_prs(self, gh, limit=20, start_date=None):
        """
        Fetch pull requests individually to updated their "mergeable" status.
        If a PR was not updated, it may not cause a real Github call (but a 304)
        """

        def get_filter(start_date):
            filter = self.issues.filter(
                # only open pull requests
                models.Q(is_pull_request=True, state='open')
                &
                (
                    # that are not merged or with unknown merged status
                    models.Q(merged=False)
                    |
                    models.Q(merged__isnull=True)
                )
            )
            if start_date:
                filter = filter.filter(updated_at__lt=start_date)
            return filter

        def action(gh, pr):
            mergeable = pr.mergeable
            mergeable_state = pr.mergeable_state
            pr.fetch_pr(gh, force_fetch=False)
            if pr.mergeable != mergeable or pr.mergeable_state != mergeable_state:
                action.updated += 1
            if not action.last_date or pr.updated_at < action.last_date:
                action.last_date = pr.updated_at
        action.updated = 0
        action.last_date = None

        count, deleted, errors, todo = self._fetch_some_prs(get_filter(start_date),
                                                        action, gh=gh, limit=limit)

        todo = get_filter((action.last_date-timedelta(seconds=1)) if action.last_date else None).count()

        return count, action.updated, deleted, errors, todo, action.last_date

    def _fetch_some_prs(self, filter, action, gh, limit=20):
        """
        Update some PRs, with filter and things to merge depending on the mode.
        """
        prs = list(filter.order_by('-updated_at')[:limit])

        count = errors = deleted = todo = 0

        if len(prs):

            for pr in prs:
                try:
                    action(gh, pr)
                except ApiNotFoundError:
                    # the PR doen't exist anymore !
                    pr.delete()
                    deleted += 1
                except ApiError:
                    errors += 1
                else:
                    count += 1

            todo = filter.count()

        return count, deleted, errors, todo

    def fetch_unfetched_commits(self, gh, limit=20):
        """
        Fetch commits that were never fetched, for example just created with a
        sha from an IssueEvent
        """
        qs = self.commits.filter(fetched_at__isnull=True)

        commits = list(qs.order_by('-authored_at')[:limit])

        count = errors = deleted = todo = 0

        if len(commits):

            for commit in commits:
                try:
                    commit.fetch(gh, force_fetch=True)
                except ApiNotFoundError:
                    # the commit doesn't exist anymore !
                    commit.fetched_at = datetime.utcnow()
                    commit.deleted = True
                    commit.save(update_fields=['fetched_at', 'deleted'])
                    deleted += 1
                except ApiError:
                    errors += 1
                else:
                    count += 1

            todo = qs.count()

        return count, deleted, errors, todo

    @property
    def github_callable_identifiers_for_issues_events(self):
        return self.github_callable_identifiers_for_issues + [
            'events',
        ]

    def fetch_issues_events(self, gh, force_fetch=False, parameters=None,
                                                            max_pages=None):
        count = self._fetch_many('issues_events', gh,
                                 defaults={
                                    'fk': {'repository': self},
                                    'related': {'*': {'fk': {'repository': self}}},
                                },
                                 parameters=parameters,
                                 force_fetch=force_fetch,
                                 max_pages=max_pages)

        return count

    @property
    def github_callable_identifiers_for_comments(self):
        return self.github_callable_identifiers_for_issues + [
            'comments',
        ]

    @property
    def github_callable_identifiers_for_pr_comments(self):
        return self.github_callable_identifiers_for_prs + [
            'comments'
        ]

    def fetch_comments(self, gh, force_fetch=False, parameters=None,
                                                                max_pages=None):
        from .comments import IssueComment

        final_parameters = {
            'sort': IssueComment.github_date_field[1],
            'direction': IssueComment.github_date_field[2],
        }
        if parameters:
            final_parameters.update(parameters)
        return self._fetch_many('comments', gh,
                                defaults={
                                    'fk': {'repository': self},
                                    'related': {'*': {'fk': {'repository': self}}},
                                },
                                parameters=final_parameters,
                                force_fetch=force_fetch,
                                max_pages=max_pages)

    def fetch_pr_comments(self, gh, force_fetch=False, parameters=None,
                                                                max_pages=None):
        from .comments import PullRequestComment

        final_parameters = {
            'sort': PullRequestComment.github_date_field[1],
            'direction': PullRequestComment.github_date_field[2],
        }
        if parameters:
            final_parameters.update(parameters)
        return self._fetch_many('pr_comments', gh,
                                defaults={
                                    'fk': {'repository': self},
                                    'related': {'*': {'fk': {'repository': self}}},
                                },
                                parameters=final_parameters,
                                force_fetch=force_fetch,
                                max_pages=max_pages)

    @property
    def github_callable_identifiers_for_commits(self):
        return self.github_callable_identifiers + [
            'commits',
        ]

    @property
    def github_callable_identifiers_for_commit_comments(self):
        return self.github_callable_identifiers + [
            'comments',
        ]

    def fetch_commit_comments(self, gh, force_fetch=False, parameters=None,
                                                                max_pages=None):
        from .comments import CommitComment

        final_parameters = {
            'sort': CommitComment.github_date_field[1],
            'direction': CommitComment.github_date_field[2],
        }

        if not force_fetch:
            final_parameters['page'] = self.commit_comments_last_page or 1

        if CommitComment.github_reverse_order:
            force_fetch = True

        if parameters:
            final_parameters.update(parameters)
        return self._fetch_many('commit_comments', gh,
                                defaults={
                                    'fk': {'repository': self},
                                    'related': {'*': {'fk': {'repository': self}}},
                                },
                                parameters=final_parameters,
                                force_fetch=force_fetch,
                                max_pages=max_pages)

    def fetch_all(self, gh, force_fetch=False, **kwargs):
        """
        Pass "two_steps=True" to felay fetch of closed issues and comments (by
        adding a FirstFetchStep2 job that will call fetch_all_step2)
        """
        two_steps = bool(kwargs.get('two_steps', False))

        super(Repository, self).fetch_all(gh, force_fetch=force_fetch)
        self.fetch_collaborators(gh, force_fetch=force_fetch)
        self.fetch_labels(gh, force_fetch=force_fetch)

        if self.has_issues:
            self.fetch_milestones(gh, force_fetch=force_fetch)

        if two_steps:
            self.fetch_issues(gh, force_fetch=force_fetch, state='open')
            from ..tasks.repository import FirstFetchStep2
            FirstFetchStep2.add_job(self.id, gh=gh)
        else:
            self.fetch_all_step2(gh, force_fetch)
            from ..tasks.repository import FetchUnmergedPullRequests
            FetchUnmergedPullRequests.add_job(self.id, priority=-15, gh=gh, delayed_for=60*60*3)  # 3 hours

        if not self.first_fetch_done:
            self.first_fetch_done = True
            self.save(update_fields=['first_fetch_done'])

    def fetch_all_step2(self, gh, force_fetch=False, start_page=None,
                        max_pages=None, to_ignore=None, issues_state=None):
        if not to_ignore:
            to_ignore = set()

        parameters = {}
        if start_page and start_page > 1:
            parameters['page'] = start_page

        kwargs = {
            'gh': gh,
            'force_fetch': force_fetch,
            'max_pages': max_pages,
            'parameters': parameters,
        }

        counts = {}

        if 'issues' not in to_ignore:
            counts['issues'] = self.fetch_issues(parameters_prs=parameters,
                                                 state=issues_state, **kwargs)
        if 'issues_events' not in to_ignore:
            counts['issues_events'] = self.fetch_issues_events(**kwargs)
        if 'comments' not in to_ignore:
            counts['comments'] = self.fetch_comments(**kwargs)
        if 'pr_comments' not in to_ignore:
            counts['pr_comments'] = self.fetch_pr_comments(**kwargs)
        if 'commit_comments' not in to_ignore:
            counts['commit_comments'] = self.fetch_commit_comments(**kwargs)

        return counts
