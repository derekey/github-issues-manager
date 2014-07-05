# -*- coding: utf-8 -*-

from collections import OrderedDict
from operator import attrgetter
import re

from django.core.urlresolvers import reverse, reverse_lazy
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template import loader, Context
from django.template.defaultfilters import escape
from django.utils.functional import cached_property

from markdown import markdown

from limpyd import model as lmodel, fields as lfields

from core import models as core_models, get_main_limpyd_database
from core.utils import contribute_to_model, cached_method

from events.models import EventPart

from subscriptions import models as subscriptions_models


def html_content(self, body_field='body'):
    html = getattr(self, '%s_html' % body_field, None)
    if html is None:
        html = markdown(getattr(self, body_field),
                        extensions=[
                            'fenced_code',
                            'nl2br',
                            'smart_strong',
                            'sane_lists',
                            'codehilite',
                        ]
                    )
    return html


class _GithubUser(models.Model):
    AVATAR_START = re.compile('^https?://\d+\.')

    class Meta:
        abstract = True

    @property
    def hash(self):
        """
        Hash for this object representing its state at the current time, used to
        know if we have to reset an issue's cache
        """
        # we remove the subdomain of the gravatar url that may change between
        # requests to the github api for the same user with the save avatar
        # (https://0.gravatar...,  https://1.gravatar...)
        avatar_url = ''
        if self.avatar_url:
            avatar_url = self.AVATAR_START.sub('', self.avatar_url, count=1)
        return hash((self.username, avatar_url, ))

    def get_related_issues(self):
        """
        Return a list of all issues related to this user (it may be the creator,
        the assignee, or the closer)
        """
        return core_models.Issue.objects.filter(
                                                   models.Q(user=self)
                                                 | models.Q(assignee=self)
                                                 | models.Q(closed_by=self)
                                               )

contribute_to_model(_GithubUser, core_models.GithubUser)


class _Repository(models.Model):
    class Meta:
        abstract = True

    def get_reverse_kwargs(self):
        """
        Return the kwargs to use for "reverse"
        """
        return {
            'owner_username': self.owner.username,
            'repository_name': self.name,
        }

    def get_absolute_url(self):
        return reverse_lazy('front:repository:home', kwargs=self.get_reverse_kwargs())

    def get_view_url(self, url_name):
        return reverse_lazy('front:repository:%s' % url_name,
                                  kwargs=self.get_reverse_kwargs())

    def get_issues_filter_url(self):
        kwargs = self.get_reverse_kwargs()
        return reverse('front:repository:issues', kwargs=kwargs)

    def get_issues_user_filter_url_for_username(self, filter_type, username):
        """
        Return the url to filter issues of this repositories by filter_type, for
        the given username
        Calls are cached for faster access
        """
        cache_key = (self.id, filter_type, username)
        if cache_key not in self.get_issues_user_filter_url_for_username._cache:
            kwargs = self.get_reverse_kwargs()
            kwargs.update({
                'username': username,
                'user_filter_type': filter_type
            })
            self.get_issues_user_filter_url_for_username._cache[cache_key] = \
                        reverse('front:repository:user_issues', kwargs=kwargs)
        return self.get_issues_user_filter_url_for_username._cache[cache_key]
    get_issues_user_filter_url_for_username._cache = {}

    def get_create_issue_url(self):
        return reverse_lazy('front:repository:issue.create',
                                  kwargs=self.get_reverse_kwargs())

contribute_to_model(_Repository, core_models.Repository)


class _LabelType(models.Model):
    class Meta:
        abstract = True

    def get_reverse_kwargs(self):
        """
        Return the kwargs to use for "reverse"
        """
        return {
            'owner_username': self.repository.owner.username,
            'repository_name': self.repository.name,
            'label_type_id': self.id
        }

    def get_edit_url(self):
        from front.repository.dashboard.views import LabelTypeEdit
        return reverse_lazy('front:repository:%s' % LabelTypeEdit.url_name, kwargs=self.get_reverse_kwargs())

    def get_delete_url(self):
        from front.repository.dashboard.views import LabelTypeDelete
        return reverse_lazy('front:repository:%s' % LabelTypeDelete.url_name, kwargs=self.get_reverse_kwargs())

    @property
    def hash(self):
        """
        Hash for this object representing its state at the current time, used to
        know if we have to reset an issue's cache
        """
        return hash((self.id, self.name, ))

    def get_related_issues(self):
        """
        Return a list of all issues related to this label type
        """
        return core_models.Issue.objects.filter(labels__label_type=self)

contribute_to_model(_LabelType, core_models.LabelType)


class _Label(models.Model):
    class Meta:
        abstract = True

    @property
    def hash(self):
        """
        Hash for this object representing its state at the current time, used to
        know if we have to reset an issue's cache
        """
        return hash((self.id, self.name, self.color,
                     self.label_type.hash if self.label_type_id else None, ))

    def get_related_issues(self):
        """
        Return a list of all issues related to this label
        """
        return core_models.Issue.objects.filter(labels=self)

contribute_to_model(_Label, core_models.Label)


class _Milestone(models.Model):
    class Meta:
        abstract = True

    @property
    def hash(self):
        """
        Hash for this object representing its state at the current time, used to
        know if we have to reset an issue's cache
        """
        return hash((self.id, self.title, self.state, ))

    def get_related_issues(self):
        """
        Return a list of all issues related to this milestone
        """
        return core_models.Issue.objects.filter(milestone=self)

    @property
    def html_content(self):
        return html_content(self, 'description')

    @property
    def short_title(self):
        if len(self.title) > 25:
            result = self.title[:20] + u'…'
        else:
            result = self.title
        return escape(result)

    def get_reverse_kwargs(self):
        """
        Return the kwargs to use for "reverse"
        """
        return {
            'owner_username': self.repository.owner.username,
            'repository_name': self.repository.name,
            'milestone_id': self.id
        }

    def get_edit_url(self):
        from front.repository.dashboard.views import MilestoneEdit
        return reverse_lazy('front:repository:%s' % MilestoneEdit.url_name, kwargs=self.get_reverse_kwargs())

    def get_delete_url(self):
        from front.repository.dashboard.views import MilestoneDelete
        return reverse_lazy('front:repository:%s' % MilestoneDelete.url_name, kwargs=self.get_reverse_kwargs())


contribute_to_model(_Milestone, core_models.Milestone)


class _Issue(models.Model):
    class Meta:
        abstract = True

    RENDERER_IGNORE_FIELDS = set(['state', 'merged', ])

    def get_reverse_kwargs(self):
        """
        Return the kwargs to use for "reverse"
        """
        return {
            'owner_username': self.repository.owner.username,
            'repository_name': self.repository.name,
            'issue_number': self.number
        }

    def get_absolute_url(self):
        return reverse_lazy('front:repository:issue', kwargs=self.get_reverse_kwargs())

    def get_created_url(self):
        kwargs = self.get_reverse_kwargs()
        del kwargs['issue_number']
        kwargs['issue_pk'] = self.pk
        return reverse_lazy('front:repository:issue.created', kwargs=kwargs)

    def edit_field_url(self, field):
        return reverse_lazy('front:repository:issue.edit.%s' % field, kwargs=self.get_reverse_kwargs())

    def issue_comment_create_url(self):
        return reverse_lazy('front:repository:issue.comment.create', kwargs=self.get_reverse_kwargs())

    def pr_comment_create_url(self):
        if not hasattr(self, '_pr_comment_create_url'):
            self._pr_comment_create_url = reverse_lazy('front:repository:issue.pr_comment.create',
                                                       kwargs=self.get_reverse_kwargs())
        return self._pr_comment_create_url

    def ajax_files_url(self):
        return reverse_lazy('front:repository:issue.files', kwargs=self.get_reverse_kwargs())

    def ajax_commits_url(self):
        return reverse_lazy('front:repository:issue.commits', kwargs=self.get_reverse_kwargs())

    def ajax_review_url(self):
        return reverse_lazy('front:repository:issue.review', kwargs=self.get_reverse_kwargs())

    def ajax_commit_base_url(self):
        kwargs = self.get_reverse_kwargs()
        kwargs['commit_sha'] = '0' * 40
        return reverse_lazy('front:repository:issue.commit', kwargs=kwargs)

    def commit_comment_create_url(self):
        if not hasattr(self, '_commit_comment_create_url'):
            kwargs = self.get_reverse_kwargs()
            kwargs['commit_sha'] = '0' * 40
            self._commit_comment_create_url = reverse_lazy('front:repository:issue.commit_comment.create',
                                                       kwargs=kwargs)
        return self._commit_comment_create_url

    @property
    def type(self):
        return 'pull request' if self.is_pull_request else 'issue'

    @property
    def nb_authors(self):
        if not self.is_pull_request or not self.nb_commits:
            return 0
        if self.nb_commits == 1:
            return 1
        return len(set(self.commits.filter(related_commits__deleted=False)
                                   .values_list('author_name', flat=True)))

    @property
    def hash(self):
        """
        Hash for this issue representing its state at the current time, used to
        know if we have to reset an its cache
        """
        return hash((self.updated_at,
                     self.user.hash if self.user_id else None,
                     self.closed_by.hash if self.closed_by_id else None,
                     self.assignee.hash if self.assignee_id else None,
                     self.milestone.hash if self.milestone_id else None,
                     self.total_comments_count or 0,
                     ','.join(['%d' % l.hash for l in self.labels.all()]),
                ))

    def update_saved_hash(self):
        """
        Update in redis the saved hash
        """
        hash_obj, _ = Hash.get_or_connect(
                                type=self.__class__.__name__, obj_id=self.pk)
        hash_obj.hash.hset(self.hash)

    @property
    def saved_hash(self):
        """
        Return the saved hash, create it if not exist
        """
        hash_obj, created = Hash.get_or_connect(
                                type=self.__class__.__name__, obj_id=self.pk)
        if created:
            self.update_saved_hash()
        return hash_obj.hash.hget()

    def update_cached_template(self, force_regenerate=False):
        """
        Update, if needed, the cached template for the current issue.
        """
        template = 'front/repository/issues/include_issue_item_for_cache.html'

        # mnimize queries
        issue = self.__class__.objects.filter(id=self.id)\
                .select_related('user', 'assignee', 'created_by', 'milestone')\
                .prefetch_related('labels__label_type')[0]

        context = Context({
            'issue': issue,
            '__regenerate__': force_regenerate,
        })

        loader.get_template(template).render(context)

    @cached_method
    def all_commits(self, include_deleted):
        qs = self.related_commits.select_related('commit__author',
                                                 'commit__committer',
                                                 'commit__repository__owner'
                                ).order_by('commit__authored_at', 'commit__committed_at')
        if not include_deleted:
            qs = qs.filter(deleted=False)

        result = []
        for c in qs:
            c.commit.relation_deleted = c.deleted
            result.append(c.commit)

        return result

    @property
    def all_entry_points(self):
        if not hasattr(self, '_all_entry_points'):
            self._all_entry_points = list(self.pr_comments_entry_points
                                .annotate(nb_comments=models.Count('comments'))
                                .filter(nb_comments__gt=0)
                                .select_related('user', 'repository__owner')
                                .prefetch_related('comments__user'))
        return self._all_entry_points

    def get_activity(self):
        """
        Return the activity of the issue, including comments, events and
        pr_comments if it's a pull request
        """
        change_events = list(self.event_set.filter(id__in=set(
                            EventPart.objects.filter(
                                            event__is_update=True,
                                            event__issue_id=self.id,
                                        )
                                        .exclude(
                                            field__in=self.RENDERER_IGNORE_FIELDS
                                        )
                                        .values_list('event_id', flat=True)
                            )).prefetch_related('parts'))

        for event in change_events:
            event.renderer_ignore_fields = self.RENDERER_IGNORE_FIELDS

        comments = list(self.comments.select_related('user', 'repository__owner'))

        events = list(self.events.exclude(event='referenced', commit_sha__isnull=True)
                                        .select_related('user', 'repository__owner'))

        activity = change_events + comments + events

        if self.is_pull_request:
            pr_comments = list(self.pr_comments.select_related('user'))

            activity += pr_comments + self.all_commits(False)

            # group commit comments by day + commit
            cc_by_commit = {}
            for c in (core_models.CommitComment.objects
                                 .filter(commit__related_commits__issue=self)
                                 .select_related('commit', 'user')
                    ):
                cc_by_commit.setdefault(c.commit, []).append(c)

            for comments in cc_by_commit.values():
                activity += GroupedCommitComments.group_by_day(comments)

        activity.sort(key=attrgetter('created_at'))

        if self.is_pull_request:
            activity = GroupedCommits.group_in_activity(activity)
            activity = GroupedPullRequestComments.group_in_activity(activity)

        return activity

    def get_sorted_entry_points(self):
        for entry_point in self.all_entry_points:
            entry_point.last_created = list(entry_point.comments.all())[-1].created_at
        return sorted(self.all_entry_points, key=attrgetter('last_created'))

    def get_commits_per_day(self, include_deleted=False):
        if not self.is_pull_request:
            return []
        return GroupedCommits.group_by_day(
            self.all_commits(include_deleted)
        )

    def get_all_commits_per_day(self):
        return self.get_commits_per_day(True)

    @cached_property
    def nb_deleted_commits(self):
        return self.related_commits.filter(deleted=True).count()

    @property
    def html_content(self):
        return html_content(self)

contribute_to_model(_Issue, core_models.Issue)


class GroupedItems(list):
    """
    An object to regroup a list of entries of the same type:
    - in a list of activities: all entries between two entries of the activity
      list are grouped together per day ("group_in_activity")
    - per day ("group_by_day")
    Also provides an 'author' method which returns a a dict with each author and
    its number of entries
    """
    model = None
    date_field = 'created_at'
    author_field = 'user'

    @classmethod
    def group_in_activity(cls, activity):
        final_activity = []
        current_group = None

        for entry in activity:

            if isinstance(entry, cls.model):
                # we have a THING

                # create a new group if first THING in a row
                if not current_group:
                    current_group = cls()

                # add the THING to the current group
                current_group.append(entry)

            else:
                # not a THING

                # we close the current group, group its THINGs by day, and insert
                # the resulting sub groups in the activity
                if current_group:
                    final_activity.extend(cls.group_by_day(current_group))
                    # we'll want to start a fresh group
                    current_group = None

                # we add the non-THING entry in the activity
                final_activity.append(entry)

        # still some THINGs with nothing after, add a group with them
        if current_group:
            final_activity.extend(cls.group_by_day(current_group))

        return final_activity

    @classmethod
    def group_by_day(cls, entries):
        if not len(entries):
            return []

        groups = []

        for entry in entries:
            entry_datetime = getattr(entry, cls.date_field)
            entry_date = entry_datetime.date()
            if not groups or entry_date != groups[-1].start_date:
                groups.append(cls())
                groups[-1].start_date = entry_date
                groups[-1].created_at = entry_datetime
            groups[-1].append(entry)

        return groups

    @classmethod
    def get_author(cls, entry):
        author = getattr(entry, cls.author_field)
        return {
            'username': author.username,
            'avatar_url': author.avatar_url,
        }

    def authors(self):
        result = OrderedDict()

        for entry in self:
            author = self.get_author(entry)
            name = author['username']
            if name not in result:
                result[name] = author
                result[name]['count'] = 0
            result[name]['count'] += 1

        return result


class GroupedPullRequestComments(GroupedItems):
    model = core_models.PullRequestComment
    date_field = 'created_at'
    author_field = 'user'
    is_pr_comments_group = True  # for template


class GroupedCommitComments(GroupedItems):
    model = core_models.CommitComment
    date_field = 'created_at'
    author_field = 'user'
    is_commit_comments_group = True  # for template


class GroupedCommits(GroupedItems):
    model = core_models.Commit
    date_field = 'authored_at'
    author_field = 'author'
    is_commits_group = True  # for template

    @classmethod
    def get_author(cls, entry):
        if entry.author_id:
            return super(GroupedCommits, cls).get_author(entry)
        else:
            return {
                'username': entry.author_name,
                'avatar_url': None,
            }


class _Commit(models.Model):
    class Meta:
        abstract = True

    @property
    def splitted_message(self):
        LEN = 72
        ln_pos = self.message.find('\n')
        if 0 <= ln_pos < LEN:
            result = [self.message[:ln_pos], self.message[ln_pos+1:]]
            while result[1] and result[1][0] == '\n':
                result[1] = result[1][1:]
            return result
        return [self.message[:LEN], self.message[LEN:]]

    @property
    def all_entry_points(self):
        if not hasattr(self, '_all_entry_points'):
            self._all_entry_points = list(self.commit_comments_entry_points
                                .annotate(nb_comments=models.Count('comments'))
                                .filter(nb_comments__gt=0)
                                .select_related('user', 'repository__owner')
                                .prefetch_related('comments__user'))
        return self._all_entry_points


contribute_to_model(_Commit, core_models.Commit)


class _WaitingSubscription(models.Model):
    class Meta:
        abstract = True

    def can_add_again(self):
        """
        Return True if the user can add the reposiory again (it is allowed if
        the state is FAILED)
        """
        return self.state == subscriptions_models.WAITING_SUBSCRIPTION_STATES.FAILED

contribute_to_model(_WaitingSubscription, subscriptions_models.WaitingSubscription)


class _IssueComment(models.Model):
    class Meta:
        abstract = True

    @property
    def html_content(self):
        return html_content(self)

    def get_reverse_kwargs(self):
        """
        Return the kwargs to use for "reverse"
        """
        return {
            'owner_username': self.repository.owner.username,
            'repository_name': self.repository.name,
            'issue_number': self.issue.number,
            'comment_pk': self.pk,
        }

    def get_absolute_url(self):
        return reverse_lazy('front:repository:issue.comment', kwargs=self.get_reverse_kwargs())

    def get_edit_url(self):
        return reverse_lazy('front:repository:issue.comment.edit', kwargs=self.get_reverse_kwargs())

    def get_delete_url(self):
        return reverse_lazy('front:repository:issue.comment.delete', kwargs=self.get_reverse_kwargs())

contribute_to_model(_IssueComment, core_models.IssueComment)


class _PullRequestComment(models.Model):
    class Meta:
        abstract = True

    @property
    def html_content(self):
        return html_content(self)

    def get_reverse_kwargs(self):
        """
        Return the kwargs to use for "reverse"
        """
        return {
            'owner_username': self.repository.owner.username,
            'repository_name': self.repository.name,
            'issue_number': self.issue.number,
            'comment_pk': self.pk,
        }

    def get_absolute_url(self):
        return reverse_lazy('front:repository:issue.pr_comment', kwargs=self.get_reverse_kwargs())

    def get_edit_url(self):
        return reverse_lazy('front:repository:issue.pr_comment.edit', kwargs=self.get_reverse_kwargs())

    def get_delete_url(self):
        return reverse_lazy('front:repository:issue.pr_comment.delete', kwargs=self.get_reverse_kwargs())

contribute_to_model(_PullRequestComment, core_models.PullRequestComment)


class _CommitComment(models.Model):
    class Meta:
        abstract = True

    @property
    def html_content(self):
        return html_content(self)

contribute_to_model(_CommitComment, core_models.CommitComment)


class Hash(lmodel.RedisModel):

    database = get_main_limpyd_database()

    type = lfields.InstanceHashField(indexable=True)
    obj_id = lfields.InstanceHashField(indexable=True)
    hash = lfields.InstanceHashField()


@receiver(post_save, dispatch_uid="hash_check")
def hash_check(sender, instance, created, **kwargs):
    """
    Check if the hash of the object has changed since its last save and if True,
    update the Issue if its an issue, or related issues if it's a:
    - user
    - milestone
    - label_type
    - label
    """

    if not isinstance(instance, (
                        core_models.GithubUser,
                        core_models.Milestone,
                        core_models.LabelType,
                        core_models.Label,
                        core_models.Issue
                      )):
        return

    # get the limpyd instance storing the hash, create it if not exists
    hash_obj, hash_obj_created = Hash.get_or_connect(
                        type=instance.__class__.__name__, obj_id=instance.pk)

    if created:
        hash_changed = True
    else:
        hash_changed = hash_obj_created or str(instance.hash) != hash_obj.hash.hget()

    if not hash_changed:
        return

    # save the new hash
    hash_obj.hash.hset(instance.hash)

    from core.tasks.issue import UpdateIssueCacheTemplate

    if isinstance(instance, core_models.Issue):
        # if an issue, add a job to update its template
        UpdateIssueCacheTemplate.add_job(instance.id)

    else:
        # if not an issue, add a job to update the templates of all related issues
        for issue in instance.get_related_issues():
            UpdateIssueCacheTemplate.add_job(issue.id)
