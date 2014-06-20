__all__ = [
    'PullRequestFile',
]

from django.db import models

from ..managers import (
    PullRequestFileManager,
)

from .base import (
    GithubObject,
    GithubObjectWithId,
)

from .mixins import (
    WithIssueMixin,
)


class PullRequestFile(WithIssueMixin, GithubObject):
    repository = models.ForeignKey('Repository', related_name='pr_files')
    issue = models.ForeignKey('Issue', related_name='files')
    sha = models.CharField(max_length=40, blank=True, null=True)
    path = models.TextField(blank=True, null=True, db_index=True)
    status = models.CharField(max_length=32, blank=True, null=True)
    nb_additions = models.PositiveIntegerField(blank=True, null=True)
    nb_deletions = models.PositiveIntegerField(blank=True, null=True)
    nb_changes = models.PositiveIntegerField(blank=True, null=True)
    patch = models.TextField(blank=True, null=True)
    tree = models.CharField(max_length=40, blank=True, null=True)

    objects = PullRequestFileManager()

    github_matching = dict(GithubObject.github_matching)
    github_matching.update({
        'additions': 'nb_additions',
        'deletions': 'nb_deletions',
        'changes': 'nb_changes',
        'filename': 'path'
    })
    github_ignore = GithubObjectWithId.github_ignore + ('nb_additions', 'nb_deletions',
                                'nb_changes', 'path') + ('raw_url', 'contents_url', 'blob_url', )
    github_identifiers = {
        'tree': 'tree',
        'sha': 'sha',
        'path': 'path',
    }

    class Meta:
        app_label = 'core'
        ordering = ('path', )
        unique_together = (
            ('tree', 'sha', 'path',)
        )

    def __unicode__(self):
        return u'"%s" on Issue #%d' % (self.path, self.issue.number if self.issue else '?')

    @property
    def github_url(self):
        return self.repository.github_url + '/blob/%s/%s' % (self.tree, self.path)
