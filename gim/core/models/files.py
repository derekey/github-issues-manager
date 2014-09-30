__all__ = [
    'CommitFile',
    'PullRequestFile',
]

from django.db import models
from django.utils.functional import cached_property

from ..managers import (
    PullRequestFileManager,
    WithCommitManager,
)

from .base import (
    GithubObject,
    GithubObjectWithId,
)

from .mixins import (
    WithIssueMixin,
    WithCommitMixin,
)


class FileMixin(models.Model):
    path = models.TextField(blank=True, null=True, db_index=True)
    status = models.CharField(max_length=32, blank=True, null=True)
    nb_additions = models.PositiveIntegerField(blank=True, null=True)
    nb_deletions = models.PositiveIntegerField(blank=True, null=True)
    patch = models.TextField(blank=True, null=True)
    sha = models.CharField(max_length=40, blank=True, null=True)

    github_matching = dict(GithubObject.github_matching)
    github_matching.update({
        'additions': 'nb_additions',
        'deletions': 'nb_deletions',
        'filename': 'path'
    })

    class Meta:
        abstract = True


class PullRequestFile(FileMixin, WithIssueMixin, GithubObject):
    repository = models.ForeignKey('Repository', related_name='pr_files')
    issue = models.ForeignKey('Issue', related_name='files')
    tree = models.CharField(max_length=40, blank=True, null=True)

    objects = PullRequestFileManager()
    github_ignore = GithubObjectWithId.github_ignore + ('nb_additions', 'nb_deletions',
                                'path') + ('raw_url', 'contents_url', 'blob_url', 'changes')
    github_identifiers = {
        'tree': 'tree',
        'sha': 'sha',
        'path': 'path',
    }

    class Meta:
        app_label = 'core'
        ordering = ('path', )
        unique_together = (
            ('repository', 'tree', 'sha', 'path',)
        )

    def __unicode__(self):
        return u'"%s" on Issue #%d' % (self.path, self.issue.number if self.issue_id else '?')

    @property
    def github_url(self):
        return self.repository.github_url + '/blob/%s/%s' % (self.tree, self.path)


class CommitFile(FileMixin, WithCommitMixin, GithubObject):
    repository = models.ForeignKey('Repository', related_name='commit_files')
    commit = models.ForeignKey('Commit', related_name='files')

    objects = WithCommitManager()
    github_ignore = GithubObjectWithId.github_ignore + ('nb_additions', 'nb_deletions',
                                'path') + ('raw_url', 'contents_url', 'blob_url', 'changes')
    github_identifiers = {
        'commit__sha': ('commit', 'sha'),
        'sha': 'sha',
        'path': 'path',
    }

    class Meta:
        app_label = 'core'
        ordering = ('path', )
        unique_together = (
            ('commit', 'sha', 'path',)
        )

    def __unicode__(self):
        return u'"%s" on Commit #%s' % (self.path, self.commit.sha if self.commit_id else '?')

    @property
    def github_url(self):
        return self.repository.github_url + '/blob/%s/%s' % (self.commit.sha, self.path)

    @cached_property
    def tree(self):
        return self.commit.sha
