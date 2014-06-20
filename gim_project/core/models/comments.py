__all__ = [
    'CommitComment',
    'CommitCommentEntryPoint',
    'IssueComment',
    'PullRequestComment',
    'PullRequestCommentEntryPoint'
]

import re

from django.db import models

from ..managers import (
    CommitCommentEntryPointManager,
    CommitCommentManager,
    IssueCommentManager,
    PullRequestCommentEntryPointManager,
    PullRequestCommentManager,
)

from .base import (
    GithubObject,
    GithubObjectWithId,
)

from .mixins import (
    WithCommitMixin,
    WithIssueMixin,
)


class CommentMixin(models.Model):
    body = models.TextField(blank=True, null=True)
    body_html = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(db_index=True)
    updated_at = models.DateTimeField(db_index=True)

    linked_commits = models.ManyToManyField('Commit')

    class Meta:
        abstract = True

    RE_COMMITS = re.compile('https?://(?:www.)?github\.com/([\w\-\.]+)/([\w\-\.]+)/commit/([0-9a-f]+)')

    def save(self, *args, **kwargs):
        """
        If the user, which is mandatory, is not defined, use (and create if
        needed) a special user named 'user.deleted'
        Find references to other issues
        Find references to commits
        """
        from .issues import IssueEvent
        from .users import GithubUser

        if self.user_id is None:
            self.user = GithubUser.objects.get_deleted_user()
            if kwargs.get('update_fields'):
                kwargs['update_fields'].append('user')

        super(CommentMixin, self).save(*args, **kwargs)

        if not kwargs.get('updated_field') or 'body_html' in kwargs['updated_field']:
            IssueEvent.objects.check_references(self, ['body_html'])
            self.find_commits()

    def find_commits(self, jobs_priority=0):
        """
        Check all references to commits in the comment, and link them via the
        `linked_commits` m2m field.
        """
        from .commits import Commit
        from .repositories import Repository

        new_commits = self.RE_COMMITS.findall(self.body_html) if self.body_html and self.body_html.strip() else []
        existing_commits = self.linked_commits.all().select_related('repository__owner')
        existing_commits_dict = {(c.repository.owner.username, c.repository.name, c.sha): c for c in existing_commits}

        # remove removed commits
        to_remove = []
        for e_tuple, e_commit in existing_commits_dict.items():
            found = False
            for new in new_commits:
                if (e_tuple[0], e_tuple[1], e_tuple[2][:len(new[2])]) == new:
                    found = True
                    break
            if not found:
                to_remove.append(e_commit)

        if to_remove:
            self.linked_commits.remove(*to_remove)

        # add new commits if we have them
        to_add, not_found = [], []
        for new in new_commits:

            # check if this new one is already in existing ones
            found = False
            for e_tuple in existing_commits_dict.keys():
                if new == (e_tuple[0], e_tuple[1], e_tuple[2][:len(new[2])]):
                    found = True
                    break
            if found:
                continue

            # try to find the commit to add
            try:
                to_add.append(Commit.objects.get(
                    repository__owner__username=new[0],
                    repository__name=new[1],
                    sha__startswith=new[2]
                ))
            except Commit.DoesNotExist:
                not_found.append(new)

        if to_add:
            self.linked_commits.add(*to_add)

        if not_found:
            from ..tasks.commit import FetchCommitBySha
            if isinstance(self, IssueComment):
                from ..tasks.comment import SearchReferenceCommitForComment as JobModel
            elif isinstance(self, PullRequestComment):
                from ..tasks.comment import SearchReferenceCommitForPRComment as JobModel
            else:
                from ..tasks.comment import SearchReferenceCommitForCommitComment as JobModel

            repos = {}
            for new in not_found:
                repo_tuple = (new[0], new[1])
                if (repo_tuple) not in repos:
                    try:
                        repos[repo_tuple] = Repository.objects.get(
                            owner__username=new[0],
                            name=new[1]
                        )
                    except Repository.DoesNotExist:
                        continue

                FetchCommitBySha.add_job('%s#%s' % (repos[repo_tuple].id, new[2]),
                                                    priority=jobs_priority)
                JobModel.add_job(self.id, delayed_for=30,
                                 repository_id=repos[repo_tuple].id, commit_sha=new[2],
                                 priority=jobs_priority)


class IssueComment(CommentMixin, WithIssueMixin, GithubObjectWithId):
    repository = models.ForeignKey('Repository', related_name='comments')
    issue = models.ForeignKey('Issue', related_name='comments')
    user = models.ForeignKey('GithubUser', related_name='issue_comments')

    objects = IssueCommentManager()

    github_format = '.full+json'
    github_ignore = GithubObjectWithId.github_ignore + ('url', 'html_url', 'issue_url', 'body_text', )
    github_edit_fields = {
        'create': ('body', ),
        'update': ('body', )
    }
    github_date_field = ('updated_at', 'updated', 'desc')

    class Meta:
        app_label = 'core'
        ordering = ('created_at', )

    @property
    def github_url(self):
        return self.issue.github_url + '#issuecomment-%s' % self.github_id

    def __unicode__(self):
        return u'on issue #%d' % (self.issue.number if self.issue else '?')

    @property
    def github_callable_identifiers(self):
        return self.repository.github_callable_identifiers_for_issues + [
            'comments',
            self.github_id,
        ]

    @property
    def github_callable_create_identifiers(self):
        return self.issue.github_callable_identifiers_for_comments


class CommentEntryPointMixin(GithubObject):
    commit_sha = models.CharField(max_length=40, blank=True, null=True)
    position = models.PositiveIntegerField(blank=True, null=True)
    path = models.TextField(blank=True, null=True)
    diff_hunk = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(db_index=True, blank=True, null=True)
    updated_at = models.DateTimeField(db_index=True, blank=True, null=True)

    class Meta:
        abstract = True

    def update_starting_point(self, save=True):
        try:
            first_comment = self.comments.all()[0]
        except IndexError:
            pass
        else:
            if self.created_at != first_comment.created_at or self.user != first_comment.user:
                self.created_at = first_comment.created_at
                self.user = first_comment.user
                if save:
                    self.save(update_fields=['created_at', 'user'])
                return True
        return False

    def save(self, *args, **kwargs):
        if self.pk:
            self.update_starting_point(save=False)
        super(CommentEntryPointMixin, self).save(*args, **kwargs)


class PullRequestCommentEntryPoint(CommentEntryPointMixin):
    repository = models.ForeignKey('Repository', related_name='pr_comments_entry_points')
    issue = models.ForeignKey('Issue', related_name='pr_comments_entry_points')
    user = models.ForeignKey('GithubUser', related_name='pr_comments_entry_points', blank=True, null=True)

    original_commit_sha = models.CharField(max_length=40, blank=True, null=True)
    original_position = models.PositiveIntegerField(blank=True, null=True)

    objects = PullRequestCommentEntryPointManager()

    github_matching = dict(GithubObject.github_matching)
    github_matching.update({
        'commit_id': 'commit_sha',
        'original_commit_id': 'original_commit_sha',
    })
    github_ignore = GithubObject.github_ignore + ('id', 'commit_sha', 'original_commit_sha'
                                        ) + ('body_text', 'url', 'html_url', 'pull_request_url', )

    github_identifiers = {
        'repository__github_id': ('repository', 'github_id'),
        'issue__number': ('issue', 'number'),
        'original_commit_sha': 'original_commit_sha',
        'path': 'path',
        'original_position': 'original_position',
    }

    class Meta:
        app_label = 'core'
        ordering = ('created_at', )
        unique_together = (
            ('issue', 'original_commit_sha', 'path', 'original_position')
        )

    def __unicode__(self):
        return u'Entry point on PR #%d' % self.issue.number

    @property
    def github_url(self):
        if not self.commit_sha:
            return None
        url = self.repository.github_url + '/blob/%s/%s' % (self.commit_sha, self.path)
        if self.position:
            url += '#L%s' % self.position
        return url


class PullRequestComment(CommentMixin, WithIssueMixin, GithubObjectWithId):
    repository = models.ForeignKey('Repository', related_name='pr_comments')
    issue = models.ForeignKey('Issue', related_name='pr_comments')
    user = models.ForeignKey('GithubUser', related_name='pr_comments')

    entry_point = models.ForeignKey('PullRequestCommentEntryPoint', related_name='comments')

    objects = PullRequestCommentManager()

    github_ignore = GithubObjectWithId.github_ignore + ('entry_point', ) + (
                        'body_text', 'url', 'html_url', 'pull_request_url', )
    github_format = '.full+json'
    github_edit_fields = {
        'create': (
           'body',
           ('commit_id', 'entry_point__original_commit_sha'),
           ('path', 'entry_point__path'),
           ('position', 'entry_point__original_position'),
        ),
        'update': (
           'body',
           ('commit_id', 'entry_point__original_commit_sha'),
           ('path', 'entry_point__path'),
           ('position', 'entry_point__original_position'),
        ),
    }
    github_date_field = ('updated_at', 'updated', 'desc')

    class Meta:
        app_label = 'core'
        ordering = ('created_at', )

    @property
    def github_url(self):
        return self.repository.github_url + '/pull/%s#discussion_r%s' % (
                                                    self.issue.number, self.github_id)

    def __unicode__(self):
        return u'on PR #%d' % (self.issue.number if self.issue else '?')

    @property
    def github_callable_identifiers(self):
        return self.repository.github_callable_identifiers_for_pr_comments + [
            self.github_id,
        ]

    @property
    def github_callable_create_identifiers(self):
        return self.issue.github_callable_identifiers_for_pr_comments

    def save(self, *args, **kwargs):
        """
        If it's a creation, update the pr_comments_count of the issue
        If it's an update, update the starting point of the entry-point
        """
        is_new = not bool(self.pk)
        super(PullRequestComment, self).save(*args, **kwargs)
        if is_new:
            self.issue.update_pr_comments_count()
        else:
            self.entry_point.update_starting_point(save=True)


class CommitCommentEntryPoint(CommentEntryPointMixin):
    repository = models.ForeignKey('Repository', related_name='commit_comments_entry_points')
    commit = models.ForeignKey('Commit', related_name='commit_comments_entry_point', null=True)
    user = models.ForeignKey('GithubUser', related_name='commit_comments_entry_points', blank=True, null=True)

    objects = CommitCommentEntryPointManager()

    github_matching = dict(GithubObject.github_matching)
    github_matching.update({
        'commit_id': 'commit_sha',
    })
    github_ignore = GithubObject.github_ignore + ('id', 'commit_sha') + (
                                        'body_text', 'url', 'html_url', )
    github_identifiers = {
        'repository__github_id': ('repository', 'github_id'),
        'commit_sha': 'commit_sha',
        'path': 'path',
        'position': 'position',
    }

    class Meta:
        app_label = 'core'
        ordering = ('created_at', )
        unique_together = (
            ('repository', 'commit_sha', 'path', 'position')
        )

    def __unicode__(self):
        return u'Entry point on commit #%s' % self.commit_sha

    @property
    def github_url(self):
        if not self.commit_sha:
            return None
        if self.path:
            return self.comments.github_url
        else:
            return self.repository.github_url + '/commit/%s#all_commit_comments' % self.commit_sha

    def save(self, *args, **kwargs):
        """
        Try to get the commit if not set, using the sha, or ask for it to be
        fetched from github
        """
        if not self.commit_id:
            self.commit, _ = self.repository.commits.get_or_create(
                sha=self.commit_sha,
            )
            from ..tasks.commit import FetchCommitBySha
            FetchCommitBySha.add_job('%s#%s' % (self.repository_id, self.commit_sha))

        super(CommitCommentEntryPoint, self).save(*args, **kwargs)


class CommitComment(CommentMixin, WithCommitMixin, GithubObjectWithId):
    repository = models.ForeignKey('Repository', related_name='commit_comments')
    user = models.ForeignKey('GithubUser', related_name='commit_comments')

    commit = models.ForeignKey('Commit', related_name='commit_comments', null=True)
    commit_sha = models.CharField(max_length=40)

    entry_point = models.ForeignKey('CommitCommentEntryPoint', related_name='comments')

    objects = CommitCommentManager()

    github_matching = dict(GithubObjectWithId.github_matching)
    github_matching.update({
        'commit_id': 'commit_sha',
    })

    github_ignore = GithubObjectWithId.github_ignore + ('entry_point', ) + (
                        'body_text', 'url', 'html_url', )
    github_format = '.full+json'
    github_edit_fields = {
        'create': (
           'body',
           ('sha', 'entry_point__commit_sha'),
           ('path', 'entry_point__path'),
           ('position', 'entry_point__position'),
        ),
        'update': (
           'body',
           ('sha', 'entry_point__commit_sha'),
           ('path', 'entry_point__path'),
           ('position', 'entry_point__position'),
        ),
    }
    github_date_field = ('created_at', 'created', 'asc')
    github_reverse_order = True

    class Meta:
        app_label = 'core'
        ordering = ('created_at', )

    @property
    def github_url(self):
        return self.repository.github_url + '/commit/%s#commitcomment-%s' % (
                                                    self.commit_sha, self.github_id)

    def __unicode__(self):
        return u'on commit #%s' % self.commit_sha

    @property
    def github_callable_identifiers(self):
        return self.repository.github_callable_identifiers_for_commit_comments + [
            self.github_id,
        ]

    @property
    def github_callable_create_identifiers(self):
        return self.issue.github_callable_identifiers_for_commit_comments

    def save(self, *args, **kwargs):
        """
        Try to get the commit if not set, using the sha, or ask for it to be
        fetched from github
        If it's a creation, update the comments_count of the commit
        If it's an update, update the starting point of the entry-point
        """
        is_new = not bool(self.pk)

        if not self.commit_id:
            self.commit, _ = self.repository.commits.get_or_create(
                sha=self.commit_sha,
            )
            from ..tasks.commit import FetchCommitBySha
            FetchCommitBySha.add_job('%s#%s' % (self.repository_id, self.commit_sha))

        super(CommitComment, self).save(*args, **kwargs)

        if is_new:
            self.commit.update_comments_count()
        else:
            self.entry_point.update_starting_point(save=True)
