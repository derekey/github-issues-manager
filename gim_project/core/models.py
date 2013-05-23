
from django.db import models
from django.contrib.auth.models import AbstractUser

import username_hack  # force the username length to be 255 chars


class GithubObject(models.Model):
    fetched_at = models.DateTimeField()

    class Meta:
        abstract = True


class GithubObjectWithId(GithubObject):
    github_id = models.PositiveIntegerField(unique=True)

    class Meta:
        abstract = True


class GithubUser(GithubObjectWithId, AbstractUser):
    # username will hold the github "login"
    token = models.TextField()
    avatar_url = models.TextField()
    is_organization = models.BooleanField(default=False)


class Repository(GithubObjectWithId):
    owner = models.ForeignKey(GithubUser, related_name='owned_repositories')
    name = models.TextField(db_index=True)
    description = models.TextField(blank=True, null=True)
    collaborators = models.ManyToManyField(GithubUser, related_name='repositories')

    class Meta:
        unique_together = (
            ('owner', 'name'),
        )


class LabelType(models.Model):
    repository = models.ForeignKey(Repository, related_name='label_types')
    regex = models.TextField()
    name = models.TextField(db_index=True)

    class Meta:
        unique_together = (
            ('repository', 'name'),
        )

    def match(self, name):
        pass

    def get_typed_name(self, name):
        pass


class Label(GithubObject):
    repository = models.ForeignKey(Repository, related_name='labels')
    name = models.TextField()
    color = models.CharField(max_length=6)
    label_type = models.ForeignKey(LabelType, related_name='labels', blank=True, null=True)
    typed_name = models.TextField(db_index=True)

    class Meta:
        unique_together = (
            ('repository', 'name'),
        )
        ordering = ('name', )

    def save(self, *args, **kwargs):
        for label_type in self.repository.label_types.all():
            if label_type.match(self.name):
                self.label_type = label_type
                self.typed_name = label_type.get_typed_name(self.name)
                break
        if not self.label_type:
            self.typed_name = self.name

        super(Label, self).save(*args, **kwargs)


class Milestone(GithubObjectWithId):
    repository = models.ForeignKey(Repository, related_name='milestones')
    number = models.PositiveIntegerField(db_index=True)
    title = models.TextField(db_index=True)
    description = models.TextField(blank=True, null=True)
    state = models.CharField(max_length=10, db_index=True)
    created_at = models.DateTimeField(db_index=True)
    due_on = models.DateTimeField(db_index=True, blank=True, null=True)
    creator = models.ForeignKey(GithubUser, related_name='milestones')

    class Meta:
        unique_together = (
            ('repository', 'number'),
        )
        ordering = ('number', )


class Issue(GithubObjectWithId):
    repository = models.ForeignKey(Repository, related_name='issues')
    number = models.PositiveIntegerField(db_index=True)
    title = models.TextField(db_index=True)
    body = models.TextField(blank=True, null=True)
    labels = models.ManyToManyField(Label, related_name='issues')
    user = models.ForeignKey(GithubUser, related_name='created_issues')
    assignee = models.ForeignKey(GithubUser, related_name='assigned_issues', blank=True, null=True)
    created_at = models.DateTimeField(db_index=True)
    updated_at = models.DateTimeField(db_index=True)
    closed_at = models.DateTimeField(blank=True, null=True)
    is_pull_request = models.BooleanField(default=False, db_index=True)
    milestone = models.ForeignKey(Milestone, related_name='issues', blank=True, null=True)
    state = models.CharField(max_length=10, db_index=True)

    class Meta:
        unique_together = (
            ('repository', 'number'),
        )


class IssueComment(GithubObjectWithId):
    issue = models.ForeignKey(Issue, related_name='comments')
    user = models.ForeignKey(GithubUser, related_name='issue_comments')
    body = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(db_index=True)
    updated_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ('created_at', )
