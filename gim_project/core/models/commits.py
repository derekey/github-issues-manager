__all__ = [
    'Commit',
    'IssueCommits',
]

from datetime import datetime

from django.db import models

from ..managers import (
    CommitManager,
    IssueCommitsManager,
)

from .base import (
    GithubObject,
    GithubObjectWithId,
)

from .mixins import (
    WithRepositoryMixin,
)


class Commit(WithRepositoryMixin, GithubObject):
    repository = models.ForeignKey('Repository', related_name='commits')
    author = models.ForeignKey('GithubUser', related_name='commits_authored', blank=True, null=True)
    committer = models.ForeignKey('GithubUser', related_name='commits_commited', blank=True, null=True)
    sha = models.CharField(max_length=40, db_index=True)
    message = models.TextField(blank=True, null=True)
    author_name = models.TextField(blank=True, null=True)
    author_email = models.CharField(max_length=256, blank=True, null=True)
    committer_name = models.TextField(blank=True, null=True)
    committer_email = models.CharField(max_length=256, blank=True, null=True)
    authored_at = models.DateTimeField(db_index=True, blank=True, null=True)
    committed_at = models.DateTimeField(db_index=True, blank=True, null=True)
    comments_count = models.PositiveIntegerField(blank=True, null=True)
    tree = models.CharField(max_length=40, blank=True, null=True)
    deleted = models.BooleanField(default=False, db_index=True)
    files_fetched_at = models.DateTimeField(blank=True, null=True)
    nb_additions = models.PositiveIntegerField(blank=True, null=True)
    nb_deletions = models.PositiveIntegerField(blank=True, null=True)
    nb_changed_files = models.PositiveIntegerField(blank=True, null=True)
    commit_comments_fetched_at = models.DateTimeField(blank=True, null=True)
    commit_comments_etag = models.CharField(max_length=64, blank=True, null=True)
    # this list is not ordered, we must memorize the last page
    commit_comments_last_page = models.PositiveIntegerField(blank=True, null=True)

    objects = CommitManager()

    # we keep old commits for reference
    delete_missing_after_fetch = False

    class Meta:
        app_label = 'core'
        ordering = ('committed_at', )
        unique_together = (
            ('repository', 'sha'),
        )

    github_identifiers = {'repository__github_id': ('repository', 'github_id'), 'sha': 'sha'}

    github_matching = dict(GithubObjectWithId.github_matching)
    github_matching.update({
        'comment_count': 'comments_count',
        'additions': 'nb_additions',
        'deletions': 'nb_deletions',
    })
    github_ignore = GithubObject.github_ignore + ('deleted', 'comments_count',
        'nb_additions', 'nb_deletions') + ('url', 'parents', 'comments_url',
        'html_url', 'commit', )

    @property
    def github_url(self):
        return self.repository.github_url + '/commit/%s' % self.sha

    def __unicode__(self):
        return u'%s' % self.sha

    @property
    def github_callable_identifiers(self):
        return self.repository.github_callable_identifiers_for_commits + [
            self.sha,
        ]

    @property
    def created_at(self):
        return self.authored_at

    def update_comments_count(self):
        self.comments_count = self.commit_comments.count()
        self.save(update_fields=['comments_count'])

    def fetch(self, gh, defaults=None, force_fetch=False, parameters=None,
                                                        meta_base_name=None):
        if defaults is None:
            defaults = {}
        defaults.setdefault('related', {}).setdefault('*', {}).setdefault('fk', {})['commit'] = self
        return super(Commit, self).fetch(gh, defaults, force_fetch, parameters, meta_base_name)

    def save(self, *args, **kwargs):
        """
        Handle case where author/commiter computer have dates in the future: in
        this case, set these dates to now, to avoid inexpected rendering
        """
        now = datetime.utcnow()
        if self.authored_at and self.authored_at > now:
            self.authored_at = now
        if self.committed_at and self.committed_at > now:
            self.committed_at = now

        if self.pk and self.nb_changed_files is None:
            self.nb_changed_files = self.files.count()
            if 'update_fields' in kwargs:
                kwargs['update_fields'].append('nb_changed_files')

        return super(Commit, self).save(*args, **kwargs)

    @property
    def github_callable_identifiers_for_commit_comments(self):
        return self.github_callable_identifiers + [
            'comments',
        ]

    def fetch_comments(self, gh, force_fetch=False, parameters=None):
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
                                    'fk': {
                                        'commit': self,
                                        'repository': self.repository
                                    },
                                    'related': {'*': {
                                        'fk': {
                                            'commit': self,
                                            'repository': self.repository
                                        }
                                    }}
                                },
                                parameters=final_parameters,
                                force_fetch=force_fetch)

    def fetch_all(self, gh, force_fetch=False, **kwargs):
        super(Commit, self).fetch_all(gh, force_fetch=force_fetch)
        self.fetch_comments(gh, force_fetch=force_fetch)


class IssueCommits(models.Model):
    """
    The table to list commits related to issues, keeping commits not referenced
    anymore in the issues by setting the 'deleted' attribute to True.
    It allows to still display commit-comments on old commits (replaced via a
    rebase for example)
    """
    issue = models.ForeignKey('Issue', related_name='related_commits')
    commit = models.ForeignKey('Commit', related_name='related_commits')
    deleted = models.BooleanField(default=False, db_index=True)

    delete_missing_after_fetch = False

    objects = IssueCommitsManager()

    class Meta:
        app_label = 'core'

    def __unicode__(self):
        result = u'%s on %s'
        if self.deleted:
            result += u' (deleted)'
        return result % (self.commit.sha, self.issue.number)
