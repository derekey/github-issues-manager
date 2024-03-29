# -*- coding: utf-8 -*-

from datetime import datetime
import json
from math import ceil
from time import sleep

from django.contrib import messages
from django.core.urlresolvers import reverse_lazy
from django.db import DatabaseError
from django.http import Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404, render
from django.utils.datastructures import SortedDict
from django.utils.functional import cached_property
from django.views.generic import UpdateView, CreateView, TemplateView, DetailView

from limpyd_jobs import STATUSES

from gim.core.models import (Issue, GithubUser, LabelType, Milestone,
                             PullRequestCommentEntryPoint, IssueComment,
                             PullRequestComment, CommitComment)
from gim.core.tasks.issue import (IssueEditStateJob, IssueEditTitleJob,
                                  IssueEditBodyJob, IssueEditMilestoneJob,
                                  IssueEditAssigneeJob, IssueEditLabelsJob,
                                  IssueCreateJob, FetchIssueByNumber)
from gim.core.tasks.comment import (IssueCommentEditJob, PullRequestCommentEditJob,
                                    CommitCommentEditJob)

from gim.subscriptions.models import SUBSCRIPTION_STATES

from gim.front.mixins.views import (WithQueryStringViewMixin,
                                    LinkedToRepositoryFormViewMixin,
                                    LinkedToIssueFormViewMixin,
                                    LinkedToUserFormViewMixin,
                                    LinkedToCommitFormViewMixin,
                                    DeferrableViewPart,
                                    WithSubscribedRepositoryViewMixin,
                                    WithAjaxRestrictionViewMixin,
                                    DependsOnIssueViewMixin)

from gim.front.models import GroupedCommits
from gim.front.repository.views import BaseRepositoryView

from gim.front.utils import make_querystring

from .forms import (IssueStateForm, IssueTitleForm, IssueBodyForm,
                    IssueMilestoneForm, IssueAssigneeForm, IssueLabelsForm,
                    IssueCreateForm, IssueCreateFormFull,
                    IssueCommentCreateForm, PullRequestCommentCreateForm, CommitCommentCreateForm,
                    IssueCommentEditForm, PullRequestCommentEditForm, CommitCommentEditForm,
                    IssueCommentDeleteForm, PullRequestCommentDeleteForm, CommitCommentDeleteForm)

LIMIT_ISSUES = 300
LIMIT_USERS = 30


class UserFilterPart(DeferrableViewPart, WithSubscribedRepositoryViewMixin, TemplateView):
    auto_load = False
    relation = None

    def get_usernames(self):
        qs = getattr(self.repository, self.relation).order_by()
        return sorted(qs.values_list('username', flat=True), key=unicode.lower)

    def count_usernames(self):
        if not hasattr(self, '_count'):
            self._count = getattr(self.repository, self.relation).count()
        return self._count

    @property
    def part_url(self):
        return reverse_lazy('front:repository:%s' % self.url_name,
                            kwargs=self.repository.get_reverse_kwargs())

    def get_context_data(self, **kwargs):
        context = super(UserFilterPart, self).get_context_data(**kwargs)

        usernames = self.get_usernames()

        context.update({
            'current_repository': self.repository,

            'usernames': usernames,
            'count': len(usernames),

            'MAX_USERS': LIMIT_USERS,
            'MIN_FOR_FILTER': 20,

            'list_open': self.request.is_ajax(),
        })

        if self.request.is_ajax():
            context['issues_filter'] = {
                'querystring': self.request.GET.get('if.querystring'),
                'objects': {
                    'user_filter_type': self.request.GET.get('if.user_filter_type'),
                },
                'parts': {
                    'username': self.request.GET.get('if.username'),
                },
            }

        return context

    def get_deferred_context_data(self, **kwargs):
        context = super(UserFilterPart, self).get_deferred_context_data(**kwargs)
        context.update({
            'count': self.count_usernames(),
            'MAX_USERS': LIMIT_USERS,
        })
        return context

    def get_template_names(self):
        if self.request.is_ajax():
            return [self.list_template_name]
        else:
            return [self.template_name]

    def inherit_from_view(self, view):
        super(UserFilterPart, self).inherit_from_view(view)


class IssuesFilterCreators(UserFilterPart):
    relation = 'issues_creators'
    url_name = 'issues.filter.creators'
    template_name = 'front/repository/issues/filters/include_creators.html'
    deferred_template_name = template_name
    list_template_name = 'front/repository/issues/filters/include_creators_list.html'
    title = 'Creators'


class IssuesFilterAssigned(UserFilterPart):
    relation = 'issues_assigned'
    url_name = 'issues.filter.assigned'
    template_name = 'front/repository/issues/filters/include_assigned.html'
    deferred_template_name = template_name
    list_template_name = 'front/repository/issues/filters/include_assigned_list.html'
    title = 'Assignees'

    def get_context_data(self, **kwargs):
        context = super(IssuesFilterAssigned, self).get_context_data(**kwargs)
        context.update({
            'no_assigned_filter_url': self.repository.get_issues_user_filter_url_for_username('assigned', '__none__'),
            'someone_assigned_filter_url': self.repository.get_issues_user_filter_url_for_username('assigned', '__any__'),
        })
        return context


class IssuesFilterClosers(UserFilterPart):
    relation = 'issues_closers'
    url_name = 'issues.filter.closers'
    template_name = 'front/repository/issues/filters/include_closers.html'
    deferred_template_name = template_name
    list_template_name = 'front/repository/issues/filters/include_closers_list.html'
    title = 'Closed by'


class IssuesView(WithQueryStringViewMixin, BaseRepositoryView):
    name = 'Issues'
    url_name = 'issues'
    template_name = 'front/repository/issues/base.html'
    default_qs = 'state=open'

    allowed_filters = ['milestone', 'state', 'labels', 'sort', 'direction',
                       'group_by', 'group_by_direction', 'pr', 'mergeable']
    allowed_states = ['open', 'closed']
    allowed_prs = ['no', 'yes']
    allowed_mergeables = ['no', 'yes']
    allowed_sort_fields = ['created', 'updated', ]
    allowed_sort_orders = ['asc', 'desc']
    allowed_group_by_fields = ['state', 'creator', 'assigned', 'closed by', 'milestone', 'pull-request']
    allowed_group_by_fields_matching = {'creator': 'user', 'assigned': 'assignee', 'pull-request': 'is_pull_request', 'closed by': 'closed_by'}
    default_sort = ('updated', 'desc')

    def _get_state(self, qs_parts):
        """
        Return the valid state to use, or None
        """
        state = qs_parts.get('state', None)
        if state in self.allowed_states:
            return state
        return None

    def _get_is_pull_request(self, qs_parts):
        """
        Return the valid "is_pull_request" flag to use, or None
        """
        is_pull_request = qs_parts.get('pr', None)
        if is_pull_request in self.allowed_prs:
            return True if is_pull_request == 'yes' else False
        return None

    def _get_is_mergeable(self, qs_parts):
        """
        Return the valid "is_mergeable" flag to use, or None
        Will return None if current filter is not on Pull requests
        """
        is_mergeable = qs_parts.get('mergeable', None)
        if is_mergeable in self.allowed_mergeables:
            if self._get_is_pull_request(qs_parts):
                return True if is_mergeable == 'yes' else False
        return None

    def _get_milestone(self, qs_parts):
        """
        Return the valid milestone to use, or None.
        A valid milestone can be '__none__' or a real Milestone object, based on a
        milestone number found in the querystring
        """
        milestone_number = qs_parts.get('milestone', None)
        if milestone_number and isinstance(milestone_number, basestring):
            if milestone_number.isdigit():
                try:
                    milestone = self.repository.milestones.ready().get(number=milestone_number)
                except Milestone.DoesNotExist:
                    pass
                else:
                    return milestone
            elif milestone_number == '__none__':
                return '__none__'
        return None

    def _get_labels(self, qs_parts):
        """
        Return a tuple with two lists:
        - the list of canceled types (tuples of (id, name))
        - the list of valid labels to use. The result is a list of Label
        objects, based on names found on the querystring
        """
        label_names = qs_parts.get('labels', None)
        if label_names:
            if not isinstance(label_names, list):
                label_names = [label_names]
            label_names = [l for l in label_names if l]
        if not label_names:
            return (None, None)

        canceled_types = set()
        real_label_names = set()

        for label_name in label_names:
            if label_name.endswith(':__none__'):
                canceled_types.add(label_name[:-9])
            else:
                real_label_names.add(label_name)

        qs = self.repository.labels.ready().filter(name__in=real_label_names)
        if canceled_types:
            canceled_types = list(self.repository.label_types.filter(name__in=canceled_types)
                                                             .values_list('id', 'name'))
            qs = qs.exclude(label_type_id__in=([t[0] for t in canceled_types]))

        return canceled_types, list(qs.prefetch_related('label_type'))

    def _get_group_by(self, qs_parts):
        """
        Return the group_by field to use, and the direction.
        The group_by field can be either an allowed string, or an existing
        LabelType
        """
        group_by = qs_parts.get('group_by', None)

        if group_by in self.allowed_group_by_fields:

            # group by a simple field
            group_by = self.allowed_group_by_fields_matching.get(group_by, group_by)

        elif group_by and group_by.startswith('type:'):

            # group by a label type
            label_type_name = group_by[5:]
            try:
                label_type = self.repository.label_types.get(name=label_type_name)
            except LabelType.DoesNotExist:
                pass
            else:
                group_by = label_type

        else:
            group_by = None

        if group_by is not None:
            direction = qs_parts.get('group_by_direction', 'asc')
            if direction not in ('asc', 'desc'):
                direction = 'asc'
            return group_by, direction

        return None, None

    def _get_sort(self, qs_parts):
        """
        Return the sort field to use, and the direction. If one or both are
        invalid, the default ones are used
        """
        sort = qs_parts.get('sort', None)
        direction = qs_parts.get('direction', None)
        if sort not in self.allowed_sort_fields:
            sort = self.default_sort[0]
        if direction not in self.allowed_sort_orders:
            direction = self.default_sort[1]
        return sort, direction

    def get_issues_for_context(self, context):
        """
        Read the querystring from the context, already cut in parts,
        and check parts that can be applied to filter issues, and return
        an issues queryset ready to use
        """
        qs_parts = self.get_qs_parts(context)

        qs_filters = {}
        filter_objects = {}

        query_filters = {}

        # filter by state
        state = self._get_state(qs_parts)
        if state is not None:
            qs_filters['state'] = filter_objects['state'] = query_filters['state'] = state

        # filter by pull request status
        is_pull_request = self._get_is_pull_request(qs_parts)
        if is_pull_request is not None:
            qs_filters['pr'] = self.allowed_prs[is_pull_request]
            filter_objects['pr'] = query_filters['is_pull_request'] = is_pull_request

        # filter by mergeable status
        is_mergeable = self._get_is_mergeable(qs_parts)
        if is_mergeable is not None:
            qs_filters['mergeable'] = self.allowed_mergeables[is_mergeable]
            filter_objects['mergeable'] = query_filters['mergeable'] = is_mergeable

        # filter by milestone
        milestone = self._get_milestone(qs_parts)
        if milestone is not None:
            filter_objects['milestone'] = milestone
            if milestone == '__none__':
                qs_filters['milestone'] = '__none__'
                query_filters['milestone_id__isnull'] = True
            else:
                qs_filters['milestone'] = '%s' % milestone.number
                query_filters['milestone__number'] = milestone.number

        # the base queryset with the current filters
        queryset = self.repository.issues.ready().filter(**query_filters)

        # now filter by labels
        label_types_to_ignore, labels = self._get_labels(qs_parts)
        if label_types_to_ignore or labels:
            qs_filters['labels'] = []
            filter_objects['current_label_types'] = {}

        if label_types_to_ignore:
            queryset = queryset.exclude(labels__label_type_id__in=[t[0] for t in label_types_to_ignore])
            # we can set, and not update, as we are first to touch this
            qs_filters['labels'] = ['%s:__none__' % t[1] for t in label_types_to_ignore]
            filter_objects['current_label_types'] = {t[0]: '__none__' for t in label_types_to_ignore}

        if labels:
            filter_objects['labels'] = labels
            filter_objects['current_labels'] = []
            for label in labels:
                qs_filters['labels'].append(label.name)
                if label.label_type_id and label.label_type_id not in filter_objects['current_label_types']:
                    filter_objects['current_label_types'][label.label_type_id] = label
                elif not label.label_type_id:
                    filter_objects['current_labels'].append(label)
                queryset = queryset.filter(labels=label.id)

        # prepare order, by group then asked ordering
        order_by = []

        # do we need to group by a field ?
        group_by, group_by_direction = self._get_group_by(qs_parts)
        if group_by is not None:
            filter_objects['group_by_direction'] = qs_filters['group_by_direction'] = group_by_direction
            if isinstance(group_by, basestring):
                qs_filters['group_by'] = qs_parts['group_by']
                filter_objects['group_by'] = qs_parts['group_by']
                filter_objects['group_by_field'] = group_by
                order_by.append('%s%s' % ('-' if group_by_direction == 'desc' else '', group_by))
            else:
                qs_filters['group_by'] = 'type:%s' % group_by.name
                filter_objects['group_by'] = group_by
                filter_objects['group_by_field'] = 'label_type_grouper'

        # Do we need to select/prefetch related stuff ? If not grouping, no
        # because we assume all templates are already cached
        # TODO: select/prefetch only the stuff needed for grouping
        if group_by is not None:
            queryset = queryset.select_related(
                    'user',  # we may have a lot of different ones
                ).prefetch_related(
                    'assignee', 'closed_by', 'milestone',  # we should have only a few ones for each
                    'labels__label_type'
                )

        # and finally, asked ordering
        sort, sort_direction = self._get_sort(qs_parts)
        qs_filters['sort'] = filter_objects['sort'] = sort
        qs_filters['direction'] = filter_objects['direction'] = sort_direction
        order_by.append('%s%s_at' % ('-' if sort_direction == 'desc' else '', sort))

        # final order by, with group and wanted order
        queryset = queryset.order_by(*order_by)

        # return the queryset and some context
        filter_context = {
            'filter_objects': filter_objects,
            'qs_filters': qs_filters,
        }
        return queryset, filter_context

    def get_context_data(self, **kwargs):
        """
        Set default content for the issue views
        """
        context = super(IssuesView, self).get_context_data(**kwargs)

        # get the list of issues
        issues, filter_context = self.get_issues_for_context(context)

        # get the list of label types
        label_types = self.repository.label_types.all().prefetch_related('labels')

        # final context
        issues_url = self.repository.get_view_url(IssuesView.url_name)

        issues_filter = self.prepare_issues_filter_context(filter_context)
        context.update({
            'root_issues_url': issues_url,
            'current_issues_url': issues_url,
            'issues_filter': issues_filter,
            'no_assigned_filter_url': self.repository.get_issues_user_filter_url_for_username('assigned', '__none__'),
            'someone_assigned_filter_url': self.repository.get_issues_user_filter_url_for_username('assigned', '__any__'),
            'qs_parts_for_ttags': issues_filter['parts'],
            'label_types': label_types,
        })

        for user_filter_view in (IssuesFilterCreators, IssuesFilterAssigned, IssuesFilterClosers):
            view = user_filter_view()
            view.inherit_from_view(self)
            count = view.count_usernames()
            context[view.relation] = {
                'count': count
            }
            if count:
                part_kwargs = {
                    'issues_filter': issues_filter,
                    'root_issues_url': issues_url,
                }
                if view.relation == 'issues_assigned':
                    part_kwargs.update({
                        'no_assigned_filter_url': context['no_assigned_filter_url'],
                        'someone_assigned_filter_url': context['someone_assigned_filter_url'],
                    })
                context[view.relation]['view'] = view
                if count > LIMIT_USERS:
                    context[view.relation]['part'] = view.render_deferred(**part_kwargs)
                else:
                    context[view.relation]['part'] = view.render_part(**part_kwargs)

        context['issues'], context['issues_count'], context['limit_reached'] = self.finalize_issues(issues, context)
        context['MAX_ISSUES'] = LIMIT_ISSUES

        context['display_add_issue_btn'] = True

        return context

    def prepare_issues_filter_context(self, filter_context):
        """
        Prepare a dict to use in the template, with many informations about the
        current filter: parts (as found in the querystring), objects (to use for
        display in the template), the base querystring (without user information
        ), and the full querystring (with user informations if a assigned/created
        filter is used)
        """
        # we need a querystring without the created/assigned parts
        qs_filter_without_user = dict(filter_context['qs_filters'])
        qs_filter_without_user.pop('user_filter_type', None)
        qs_filter_without_user.pop('username', None)

        context_issues_filter = {
            'parts': filter_context['qs_filters'],
            'objects': filter_context['filter_objects'],
            'querystring': make_querystring(qs_filter_without_user),
            'querystring_with_user': make_querystring(filter_context['qs_filters']),
        }

        return context_issues_filter

    def finalize_issues(self, issues, context):
        """
        Return a final list of issues usable in the view.
        Actually simply order ("group") by a label_type if asked
        """
        total_count = issues_count = issues.count()

        if not issues_count:
            return [], 0, False

        if self.request.GET.get('limit') != 'no' and issues_count > LIMIT_ISSUES:
            issues_count = LIMIT_ISSUES
            issues = issues[:LIMIT_ISSUES]
            limit_reached = True
        else:
            limit_reached = False

        try:
            issues = list(issues.all())
        except DatabaseError, e:
            # sqlite limits the vars passed in the request to 999, and
            # prefetch_related use a in(...), and with more than 999 issues
            # sqlite raises an error.
            # In this case, we loop on the data by slice of 999 issues
            if u'%s' % e != 'too many SQL variables':
                raise
            queryset = issues
            issues = []
            per_fetch = 999

            iterations = int(ceil(issues_count / float(per_fetch)))
            for iteration in range(0, iterations):
                issues += list(queryset[iteration * per_fetch:(iteration + 1) * per_fetch])

        label_type = context['issues_filter']['objects'].get('group_by', None)
        attribute = context['issues_filter']['objects'].get('group_by_field', None)
        if label_type and isinstance(label_type, LabelType) and attribute:

            # regroup issues by label from the lab
            issues_dict = {}
            for issue in issues:
                add_to = None

                for label in issue.labels.ready():  # thanks prefetch_related
                    if label.label_type_id == label_type.id:
                        # found a label for the wanted type, mark it and stop
                        # checking labels for this issue
                        add_to = label.id
                        setattr(issue, attribute, label)
                        break

                # add in a dict, with one entry for each label of the type (and one for None)
                issues_dict.setdefault(add_to, []).append(issue)

            # for each label of the type, append matching issues to the final
            # list
            issues = []
            label_type_labels = [None] + list(label_type.labels.ready())
            if context['issues_filter']['parts'].get('group_by_direction', 'asc') == 'desc':
                label_type_labels.reverse()
            for label in label_type_labels:
                label_id = None if label is None else label.id
                if label_id in issues_dict:
                    issues += issues_dict[label_id]

        return issues, total_count, limit_reached


class UserIssuesView(IssuesView):
    url_name = 'user_issues'
    user_filter_types = ['assigned', 'created_by', 'closed_by']
    user_filter_types_matching = {'created_by': 'user', 'assigned': 'assignee', 'closed_by': 'closed_by'}
    allowed_filters = IssuesView.allowed_filters + user_filter_types

    def _get_user_filter(self, qs_parts):
        """
        Return the user filter type used, and the user to filter on. The user
        can be either the string '__none__', or a GithubUser object
        """
        filter_type = self.kwargs.get('user_filter_type', qs_parts.get('user_filter_type', None))
        username = self.kwargs.get('username', qs_parts.get('username', None))

        if username and filter_type in self.user_filter_types:
            if username == '__none__':
                return filter_type, '__none__'
            elif username == '__any__' and filter_type == 'assigned':
                return filter_type, '__any__'
            try:
                user = GithubUser.objects.get(username=username)
            except GithubUser.DoesNotExist:
                pass
            else:
                return filter_type, user

        return None, None

    def get_issues_for_context(self, context):
        """
        Update the previously done queryset by filtering by a user as assigned
        to issues, or their creator or the one who closed them
        """
        queryset, filter_context = super(UserIssuesView, self).get_issues_for_context(context)
        qs_parts = self.get_qs_parts(context)

        user_filter_type, user = self._get_user_filter(qs_parts)
        if user_filter_type and user:
            filter_context['filter_objects']['user'] = user
            filter_context['filter_objects']['user_filter_type'] = user_filter_type
            filter_context['qs_filters']['user_filter_type'] = user_filter_type
            filter_field = self.user_filter_types_matching[user_filter_type]
            filter_context['qs_filters']['username'] = user
            if user == '__none__':
                queryset = queryset.filter(**{'%s_id__isnull' % filter_field: True})
            elif user == '__any__' and user_filter_type == 'assigned':
                queryset = queryset.filter(**{'%s_id__isnull' % filter_field: False})
            else:
                filter_context['qs_filters']['username'] = user.username
                queryset = queryset.filter(**{filter_field: user.id})

        return queryset, filter_context

    def get_context_data(self, **kwargs):
        """
        Set the current base url for issues for this view
        """
        context = super(UserIssuesView, self).get_context_data(**kwargs)

        user_filter_type = context['issues_filter']['objects'].get('user_filter_type', None)
        user_filter_user = context['issues_filter']['objects'].get('user', None)
        if user_filter_type and user_filter_user:
            context['issues_filter']['objects']['current_%s' % user_filter_type] = context['issues_filter']['parts']['username']
            current_issues_url_kwargs = self.repository.get_reverse_kwargs()
            current_issues_url_kwargs.update({
                'user_filter_type': user_filter_type,
                'username': user_filter_user,
            })
            context['current_issues_url'] = reverse_lazy(
                                    'front:repository:%s' % UserIssuesView.url_name,
                                    kwargs=current_issues_url_kwargs)

        return context


class IssueView(UserIssuesView):
    url_name = 'issue'
    ajax_template_name = 'front/repository/issues/issue.html'

    def get_current_issue(self):
        """
        Based on the informations from the url, try to return
        the wanted issue
        """
        issue = None
        if 'issue_number' in self.kwargs:
            issue = self.repository.issues.ready().select_related(
                    'user',  'assignee', 'closed_by', 'milestone',
                ).prefetch_related(
                    'labels__label_type'
                ).get(number=self.kwargs['issue_number'])
        return issue

    def get_involved_people(self, issue, activity, collaborators_ids):
        """
        Return a list with a dict for each people involved in the issue, with
        the submitter first, the assignee, the the closed_by, and all comments
        authors, with only one entry per person, with, for each dict, the
        user, the comment's count as "count", and a list of types (one or many
        of "owner", "collaborator", "submitter") as "types"
        """
        involved = SortedDict()

        def add_involved(user, is_comment=False, is_commit=False):
            real_user = not isinstance(user, basestring)
            if real_user:
                key = user.username
                val = user
            else:
                key = user
                val = {'username': user}

            d = involved.setdefault(key, {
                                    'user': val, 'comments': 0, 'commits': 0})
            if real_user:
                d['user'] = val  # override if user was a dict
            if is_comment:
                d['comments'] += 1
            if is_commit:
                d['commits'] += 1

        add_involved(issue.user)

        if issue.assignee_id and issue.assignee_id not in involved:
            add_involved(issue.assignee)

        if issue.state == 'closed' and issue.closed_by_id and issue.closed_by_id not in involved:
            add_involved(issue.closed_by)

        for entry in activity:
            if isinstance(entry, PullRequestCommentEntryPoint):
                for pr_comment in entry.comments.all():
                    add_involved(pr_comment.user, is_comment=True)
            elif isinstance(entry, IssueComment):
                add_involved(entry.user, is_comment=True)
            elif isinstance(entry, GroupedCommits):
                for pr_commit in entry:
                    add_involved(pr_commit.author if pr_commit.author_id
                                                  else pr_commit.author_name,
                                 is_commit=True)

        involved = involved.values()
        for involved_user in involved:
            if isinstance(involved_user['user'], dict):
                continue
            involved_user['types'] = []
            if involved_user['user'].id == self.repository.owner_id:
                involved_user['types'].append('owner')
            elif collaborators_ids and involved_user['user'].id in collaborators_ids:
                involved_user['types'].append('collaborator')
            if involved_user['user'].id == issue.user_id:
                involved_user['types'].append('submitter')

        return involved

    def get_context_data(self, **kwargs):
        """
        Add the selected issue in the context
        """
        if self.request.is_ajax():
            # is we respond to an ajax call, bypass all the context stuff
            # done by IssuesView and UserIssuesView by calling directly
            # their baseclass
            context = super(IssuesView, self).get_context_data(**kwargs)
        else:
            context = super(IssueView, self).get_context_data(**kwargs)

        # check which issue to display
        current_issue_state = 'ok'
        current_issue = None
        try:
            current_issue = self.get_current_issue()
        except Issue.DoesNotExist:
            current_issue_state = 'notfound'
        else:
            if not current_issue:
                current_issue_state = 'undefined'

        # fetch other useful data
        edit_level = self.get_edit_level(current_issue)
        if current_issue:
            activity = current_issue.get_activity()
            involved = self.get_involved_people(current_issue, activity,
                                                    self.collaborators_ids)

            if current_issue.is_pull_request:
                context['entry_points_dict'] = self.get_entry_points_dict(
                                                current_issue.all_entry_points)

        else:
            activity = []
            involved = []

        # final context
        context.update({
            'current_issue': current_issue,
            'current_issue_state': current_issue_state,
            'current_issue_activity': activity,
            'current_issue_involved': involved,
            'current_issue_edit_level':  edit_level,
        })

        return context

    def get_edit_level(self, issue):
        """
        Return the edit level of the given issue. It may be None (read only),
        "self" or "full"
        """
        edit_level = None
        if issue and issue.number:
            if self.subscription.state in SUBSCRIPTION_STATES.WRITE_RIGHTS:
                edit_level = 'full'
            elif self.subscription.state == SUBSCRIPTION_STATES.READ\
                                    and issue.user == self.request.user:
                edit_level = 'self'

        return edit_level

    def get_entry_points_dict(self, entry_points):
        """
        Return a dict that will be used in the issue files template to display
        pull request comments (entry points).
        The first level of the dict contains path of the file with entry points.
        The second level contains the position of the entry point, with the
        PullRequestCommentEntryPoint object as value
        """
        entry_points_dict = {}
        for entry_point in entry_points:
            if not entry_point.position:
                continue
            entry_points_dict.setdefault(entry_point.path, {})[entry_point.position] = entry_point
        return entry_points_dict

    def get_template_names(self):
        """
        Use a specific template if the request is an ajax one
        """
        if self.request.is_ajax():
            self.template_name = self.ajax_template_name
        return super(IssueView, self).get_template_names()


class AskFetchIssueView(WithAjaxRestrictionViewMixin, IssueView):
    url_name = 'issue.ask-fetch'
    ajax_only = True
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        """
        Get the issue and add a new job to fetch it
        """
        try:
            issue = self.get_current_issue()
        except Exception:
            messages.error(self.request,
                'The issue from <strong>%s</strong> you asked to fetch from Github could doesn\'t exist anymore!' % (
                    self.repository))
        else:
            self.add_job(issue)

        return self.render_to_response(context={})

    def add_job(self, issue):
        """
        Add a job to fetch the issue and inform the current user
        """
        identifier = '%s#%s' % (self.repository.id, issue.number)
        user_pk_str = str(self.request.user.id)
        users_to_inform = set(user_pk_str)
        tries = 0
        while True:
            # add a job to fetch the issue, informing
            job = FetchIssueByNumber.add_job(
                    identifier=identifier,
                    priority=5,  # higher priority
                    gh=self.request.user.get_connection(),
                    users_to_inform=users_to_inform,
                    force_fetch_all=1,
            )
            # we may already have this job queued
            if user_pk_str in job.users_to_inform.smembers():
                # if it has already the correct user to inform, we're good
                break
            else:
                # the job doesn't have the correct user to inform
                if tries >= 10:
                    # we made enough tries, stop now
                    messages.error(self.request,
                        'The %s <strong>#%d</strong> from <strong>%s</strong> you asked to fetch from Github couldn\'t be fetched!' % (
                            issue.type, issue.number, self.repository.full_name))
                    return
                # ok let's cancel this job and try again
                tries += 1
                job.status.hset('c')
                job.queued.delete()
                # adding users we already have to inform to the new job
                existing_users = job.users_to_inform.smembers()
                if existing_users:
                    users_to_inform.update(existing_users)

        # ok the job was added, tell to the user...
        messages.success(self.request,
            'The %s <strong>#%d</strong> from <strong>%s</strong> you asked to fetch from Github will be updated soon' % (
                issue.type, issue.number, self.repository.full_name))

    def get_template_names(self):
        """
        We'll only display messages to the user
        """
        return ['front/messages.html']


class CreatedIssueView(IssueView):
    url_name = 'issue.created'

    def redirect_to_created_issue(self, wait_if_failure=0):
        """
        If the issue doesn't exists anymore, a new one may have been created by
        dist_edit, so redirect to the new one. Wait a little if no issue found.
        """
        try:
            job = IssueCreateJob.get(identifier=self.kwargs['issue_pk'])
            issue = Issue.objects.get(pk=job.created_pk.hget())
        except:
            if wait_if_failure > 0:
                sleep(0.1)
                return self.redirect_to_created_issue(wait_if_failure-0.1)
            else:
                raise Http404
        else:
            return HttpResponsePermanentRedirect(issue.get_absolute_url())

    def get(self, request, *args, **kwargs):
        """
        `dist-edit` delete the issue create by the user to replace it by the
        one created on github that we fetched back, but it has a new PK, saved
        in the job, so use it to get the new issue and redirect it back to its
        final url.
        Redirect to the final url too if with now have a number
        """
        try:
            issue = self.get_current_issue()
        except Issue.DoesNotExist:
            # ok, deleted/recreated by dist_edit...
            return self.redirect_to_created_issue(wait_if_failure=0.3)
        else:
            if issue.number:
                return HttpResponsePermanentRedirect(issue.get_absolute_url())

        try:
            return super(CreatedIssueView, self).get(request, *args, **kwargs)
        except Http404:
            # existed just before, but not now, just deleted/recreated by dist_edit
            return self.redirect_to_created_issue(wait_if_failure=0.3)

    def get_current_issue(self):
        """
        Based on the informations from the url, try to return the wanted issue
        """
        if not hasattr(self, '_issue'):
            self._issue = self.repository.issues.select_related(
                        'user',  'assignee', 'closed_by', 'milestone',
                    ).prefetch_related(
                        'labels__label_type'
                    ).get(pk=self.kwargs['issue_pk'])
        return self._issue


class SimpleAjaxIssueView(WithAjaxRestrictionViewMixin, IssueView):
    """
    A base class to fetch some parts of an issue via ajax.
    If not directly overriden, the template must be specified when using this
    view in urls.py
    """
    ajax_only = True

    def get_context_data(self, **kwargs):
        """
        Add the issue and its files in the context
        """
        # we bypass all the context stuff done by IssuesView by calling
        # directly its baseclass
        context = super(IssuesView, self).get_context_data(**kwargs)

        try:
            current_issue = self.get_current_issue()
        except Issue.DoesNotExist:
            raise Http404

        context['current_issue'] = current_issue
        context['current_issue_edit_level'] = self.get_edit_level(current_issue)

        return context


class FilesAjaxIssueView(SimpleAjaxIssueView):
    """
    Override SimpleAjaxIssueView to add comments in files (entry points)
    """
    ajax_template_name = 'front/repository/issues/code/include_issue_files.html'

    def get_context_data(self, **kwargs):
        context = super(FilesAjaxIssueView, self).get_context_data(**kwargs)
        context['entry_points_dict'] = self.get_entry_points_dict(
                                    context['current_issue'].all_entry_points)
        return context


class CommitViewMixin(object):
    """
    A simple mixin with a `commit` property to get the commit matching the sha
    in the url
    """
    issue_related_name = 'commit__issues'
    repository_related_name = 'commit__issues__repository'

    def get_queryset(self):
        """
        Return a queryset based on the current repository and allowed rights.
        Override the one from DependsOnIssueViewMixin to only depends on the
        repository, not the issue, to allow managing comment on commits not in
        the current issue.
        """
        return self.model._default_manager.filter(repository=self.repository)

    def set_comment_urls(self, comment, issue, kwargs=None):
        if not kwargs:
            kwargs = issue.get_reverse_kwargs()
            kwargs['commit_sha'] = self.commit.sha

        kwargs = kwargs.copy()
        kwargs['comment_pk'] = comment.id
        comment.get_edit_url = reverse_lazy('front:repository:' + CommitCommentEditView.url_name, kwargs=kwargs)
        comment.get_delete_url = reverse_lazy('front:repository:' + CommitCommentDeleteView.url_name, kwargs=kwargs)
        comment.get_absolute_url = reverse_lazy('front:repository:' + CommitCommentView.url_name, kwargs=kwargs)

    @cached_property
    def commit(self):
        return get_object_or_404(self.repository.commits, sha=self.kwargs['commit_sha'])

    def get_context_data(self, **kwargs):
        context = super(CommitViewMixin, self).get_context_data(**kwargs)
        context['current_commit'] = self.commit
        return context


class CommitAjaxIssueView(CommitViewMixin, SimpleAjaxIssueView):
    """
    Override SimpleAjaxIssueView to add commit and its comments
    """
    ajax_template_name = 'front/repository/issues/code/include_commit_files.html'

    issue_related_name = 'commit__issues'
    repository_related_name = 'commit__issues__repository'

    def get_context_data(self, **kwargs):
        context = super(CommitAjaxIssueView, self).get_context_data(**kwargs)
        context['current_commit'] = self.commit

        entry_points = self.commit.all_entry_points

        # force urls, as we are in an issue
        kwargs = context['current_issue'].get_reverse_kwargs()
        kwargs['commit_sha'] = self.commit.sha
        for entry_point in entry_points:
            for comment in entry_point.comments.all():
                self.set_comment_urls(comment, context['current_issue'], kwargs)

        context['entry_points_dict'] = self.get_entry_points_dict(entry_points)

        try:
            context['final_entry_point'] = [ep for ep in entry_points if ep.path is None][0]
        except IndexError:
            context['final_entry_point'] = None

        context['commit_comment_create_url'] = \
            context['current_issue'].commit_comment_create_url().replace('0' * 40, self.commit.sha)

        return context


class BaseIssueEditView(LinkedToRepositoryFormViewMixin):
    model = Issue
    allowed_rights = SUBSCRIPTION_STATES.READ_RIGHTS
    http_method_names = [u'get', u'post']
    ajax_only = True

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        filters = {
            'number': self.kwargs['issue_number'],
        }

        return queryset.get(**filters)

    def get_success_url(self):
        return self.object.get_absolute_url()


class IssueEditFieldMixin(BaseIssueEditView, UpdateView):
    field = None
    job_model = None
    url_name = None
    form_class = None
    template_name = 'front/one_field_form.html'

    def form_valid(self, form):
        """
        Override the default behavior to add a job to update the issue on the
        github side
        """
        response = super(IssueEditFieldMixin, self).form_valid(form)
        value = self.get_final_value(form.cleaned_data[self.field])

        self.job_model.add_job(self.object.pk,
                          gh=self.request.user.get_connection(),
                          value=value)

        messages.success(self.request, self.get_success_user_message(self.object))

        return response

    def get_final_value(self, value):
        """
        Return the value that will be pushed to githubs
        """
        return value

    def form_invalid(self, form):
        return self.render_form_errors_as_messages(form, show_fields=False)

    def get_success_user_message(self, issue):
        return u"""The <strong>%s</strong> for the %s <strong>#%d</strong> will
                be updated shortly""" % (self.field, issue.type, issue.number)

    def get_context_data(self, **kwargs):
        context = super(IssueEditFieldMixin, self).get_context_data(**kwargs)
        context['form_action'] = self.object.edit_field_url(self.field)
        context['form_classes'] = "issue-edit-field issue-edit-%s" % self.field
        return context

    def get_object(self, queryset=None):
        # use current self.object if we have it
        if getattr(self, 'object', None):
            return self.object
        return super(IssueEditFieldMixin, self).get_object(queryset)

    def current_job(self):
        self.object = self.get_object()
        try:
            job = self.job_model.collection(identifier=self.object.id, queued=1).instances()[0]
        except IndexError:
            return None
        else:
            return job

    def dispatch(self, request, *args, **kwargs):
        current_job = self.current_job()

        if current_job:
            for i in range(0, 3):
                sleep(0.1)  # wait a little, it may be fast
                current_job = self.current_job()
                if not current_job:
                    break

            if current_job:
                who = current_job.gh_args.hget('username')
                return self.render_not_editable(request, who)

        return super(IssueEditFieldMixin, self).dispatch(request, *args, **kwargs)

    def render_not_editable(self, request, who):
        if who == request.user.username:
            who = 'yourself'
        messages.warning(request, self.get_not_editable_user_message(self.object, who))
        return render(self.request, 'front/messages.html')

    def get_not_editable_user_message(self, issue, who):
        return u"""The <strong>%s</strong> for the %s <strong>#%d</strong> is
                currently being updated (asked by <strong>%s</strong>), please
                wait a few seconds and retry""" % (
                                    self.field, issue.type, issue.number, who)


class IssueEditState(LinkedToUserFormViewMixin, IssueEditFieldMixin):
    field = 'state'
    job_model = IssueEditStateJob
    url_name = 'issue.edit.state'
    form_class = IssueStateForm
    http_method_names = [u'post']

    def get_success_user_message(self, issue):
        new_state = 'reopened' if issue.state == 'open' else 'closed'
        return u'The %s <strong>#%d</strong> will be %s shortly' % (
                                            issue.type, issue.number, new_state)

    def get_not_editable_user_message(self, issue, who):
        new_state = 'reopened' if issue.state == 'open' else 'closed'
        return u"""The %s <strong>#%d</strong> is currently being %s (asked by
                <strong>%s</strong>), please wait a few seconds and retry""" % (
                                    issue.type, issue.number, new_state, who)


class IssueEditTitle(IssueEditFieldMixin):
    field = 'title'
    job_model = IssueEditTitleJob
    url_name = 'issue.edit.title'
    form_class = IssueTitleForm


class IssueEditBody(IssueEditFieldMixin):
    field = 'body'
    job_model = IssueEditBodyJob
    url_name = 'issue.edit.body'
    form_class = IssueBodyForm
    template_name = 'front/one_field_form_real_buttons.html'


class IssueEditMilestone(IssueEditFieldMixin):
    field = 'milestone'
    job_model = IssueEditMilestoneJob
    url_name = 'issue.edit.milestone'
    form_class = IssueMilestoneForm

    def get_final_value(self, value):
        """
        Return the value that will be pushed to githubs
        """
        return value.number if value else ''


class IssueEditAssignee(IssueEditFieldMixin):
    field = 'assignee'
    job_model = IssueEditAssigneeJob
    url_name = 'issue.edit.assignee'
    form_class = IssueAssigneeForm

    def get_final_value(self, value):
        """
        Return the value that will be pushed to githubs
        """
        return value.username if value else ''


class IssueEditLabels(IssueEditFieldMixin):
    field = 'labels'
    job_model = IssueEditLabelsJob
    url_name = 'issue.edit.labels'
    form_class = IssueLabelsForm

    def get_final_value(self, value):
        """
        Return the value that will be pushed to githubs. We encode the list of
        labels as json to be stored in the job single field
        """
        labels = [l.name for l in value] if value else []
        return json.dumps(labels)

    def get_not_editable_user_message(self, issue, who):
        return u"""The <strong>%s</strong> for the %s <strong>#%d</strong> are
                currently being updated (asked by <strong>%s</strong>), please
                wait a few seconds and retry""" % (
                                    self.field, issue.type, issue.number, who)


class IssueCreateView(LinkedToUserFormViewMixin, BaseIssueEditView, CreateView):
    url_name = 'issue.create'
    template_name = 'front/repository/issues/create.html'
    ajax_only = False

    def get_form_class(self):
        """
        Not the same form depending of the rights
        """
        if self.subscription.state in SUBSCRIPTION_STATES.WRITE_RIGHTS:
            return IssueCreateFormFull
        return IssueCreateForm

    def get_success_url(self):
        if self.object.number:
            return super(IssueCreateView, self).get_success_url()
        return self.object.get_created_url()

    def form_valid(self, form):
        """
        Override the default behavior to add a job to create the issue on the
        github side
        """
        response = super(IssueCreateView, self).form_valid(form)

        # create the job
        job = IssueCreateJob.add_job(self.object.pk,
                               gh=self.request.user.get_connection())

        # try to wait just a little for the job to be done
        for i in range(0, 3):
            sleep(0.1)  # wait a little, it may be fast
            if job.status.hget() == STATUSES.SUCCESS:
                self.object = Issue.objects.get(pk=job.created_pk.hget())
                break

        if self.object.number:
            # if job done, it would have create the message itself
            # and we want to be sure to redirect to the good url now that the
            # issue was created
            return HttpResponseRedirect(self.get_success_url())
        else:
            messages.success(self.request, self.get_success_user_message(self.object))
            return response

    def get_success_user_message(self, issue):
        title = issue.title
        if len(title) > 30:
            title = title[:30] + u'…'
        return u"""The %s "<strong>%s</strong>" will
                be created shortly""" % (issue.type, title)


class BaseIssueCommentView(WithAjaxRestrictionViewMixin, DependsOnIssueViewMixin, DetailView):
    context_object_name = 'comment'
    pk_url_kwarg = 'comment_pk'
    http_method_names = ['get']
    ajax_only = True

    def get_context_data(self, **kwargs):
        context = super(BaseIssueCommentView, self).get_context_data(**kwargs)

        context.update({
            'use_current_user': False,
            'include_create_form': self.request.GET.get('include_form', False),
        })

        return context

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()

        pk = self.kwargs['comment_pk']
        object = None

        try:
            object = queryset.get(pk=pk)
        except self.model.DoesNotExist:
            # maybe the object was deleted and recreated by dist_edit
            try:
                job = self.job_model.get(identifier=pk, mode='create')
            except self.job_model.DoesNotExist:
                pass
            else:
                to_wait = 0.3
                while to_wait > 0:
                    created_pk = job.created_pk.hget()
                    if created_pk:
                        object = queryset.get(pk=created_pk)
                        break
                    sleep(0.1)

        if not object:
            raise Http404("No comment found matching the query")

        return object


class IssueCommentView(BaseIssueCommentView):
    url_name = 'issue.comment'
    model = IssueComment
    template_name = 'front/repository/issues/comments/include_issue_comment.html'
    job_model = IssueCommentEditJob


class PullRequestCommentView(BaseIssueCommentView):
    url_name = 'issue.pr_comment'
    model = PullRequestComment
    template_name = 'front/repository/issues/comments/include_code_comment.html'
    job_model = PullRequestCommentEditJob

    def get_context_data(self, **kwargs):
        context = super(PullRequestCommentView, self).get_context_data(**kwargs)

        context.update({
            'entry_point': self.object.entry_point,
        })

        return context


class CommitCommentView(CommitViewMixin, BaseIssueCommentView):
    url_name = 'issue.commit_comment'
    model = CommitComment
    template_name = 'front/repository/issues/comments/include_commit_comment.html'
    job_model = CommitCommentEditJob

    repository_related_name = 'commit__issues__repository'

    def get_object(self, *args, **kwargs):
        obj = super(CommitCommentView, self).get_object(*args, **kwargs)
        if obj:
            # force urls, as we are in an issue
            self.set_comment_urls(obj, self.issue)
        return obj

    def get_context_data(self, **kwargs):
        context = super(CommitCommentView, self).get_context_data(**kwargs)

        context.update({
            'current_commit': self.commit,
            'entry_point': self.object.entry_point,
        })

        return context


class IssueCommentEditMixin(object):
    model = IssueComment
    job_model = IssueCommentEditJob


class PullRequestCommentEditMixin(object):
    model = PullRequestComment
    job_model = PullRequestCommentEditJob


class CommitCommentEditMixin(LinkedToCommitFormViewMixin, CommitViewMixin):
    model = CommitComment
    job_model = CommitCommentEditJob

    def obj_message_part(self):
        return 'commit <strong>#%s</strong> (%s <strong>#%s</strong>)' % (
            self.commit.sha[:7], self.issue.type, self.issue.number)

    def get_success_url(self):
        kwargs = self.issue.get_reverse_kwargs()
        kwargs['commit_sha'] = self.commit.sha
        kwargs['comment_pk'] = self.object.id
        return reverse_lazy('front:repository:' + CommitCommentView.url_name, kwargs=kwargs)

    def get_object(self, *args, **kwargs):
        obj = super(CommitCommentEditMixin, self).get_object(*args, **kwargs)
        if obj:
            # force urls, as we are in an issue
            self.set_comment_urls(obj, self.issue)
        return obj


class BaseCommentEditMixin(LinkedToUserFormViewMixin, LinkedToIssueFormViewMixin):
    ajax_only = True
    http_method_names = ['get', 'post']
    edit_mode = None

    def obj_message_part(self):
        return '%s <strong>#%s</strong>' % (self.issue.type, self.issue.number)

    def form_valid(self, form):
        """
        Override the default behavior to add a job to create the comment on the
        github side
        """
        response = super(BaseCommentEditMixin, self).form_valid(form)

        self.job_model.add_job(self.object.pk,
                               mode=self.edit_mode,
                               gh=self.request.user.get_connection())

        messages.success(self.request,
            u'Your comment on the %s will be %s shortly' % (
                                self.obj_message_part(), self.verb))

        return response


class BaseCommentCreateView(BaseCommentEditMixin, CreateView):
    edit_mode = 'create'
    verb = 'created'
    http_method_names = ['post']

    def get_success_url(self):
        url = super(BaseCommentCreateView, self).get_success_url()
        return url + '?include_form=1'


class IssueCommentCreateView(IssueCommentEditMixin, BaseCommentCreateView):
    url_name = 'issue.comment.create'
    form_class = IssueCommentCreateForm


class CommentWithEntryPointCreateViewMixin(BaseCommentCreateView):
    null_path_allowed = False
    sha_field = ''

    def get_diff_hunk(self, file, position):
        if not file:
            return ''
        return'\n'.join(file.patch.split('\n')[:position+1])

    @property
    def parent_object(self):
        raise NotImplementedError()

    def get_entry_point(self, sha=None):
        obj = self.parent_object

        if 'entry_point_id' in self.request.POST:
            entry_point_id = self.request.POST['entry_point_id']
            self.entry_point = getattr(obj, self.entry_point_related_name).get(id=entry_point_id)
        else:
            # get and check entry-point params

            if self.request.POST.get('position', None) is None and self.null_path_allowed:
                position = None
            elif len(self.request.POST['position']) < 10:
                position = int(self.request.POST['position'])
            else:
                raise KeyError('position')

            if sha is None:
                if len(self.request.POST['sha']) == 40:
                    sha = self.request.POST['sha']
                else:
                    raise KeyError('sha')

            if self.request.POST.get('path', None) is None and self.null_path_allowed:
                path = None
                file = None
            else:
                path = self.request.POST['path']
                try:
                    file = obj.files.get(path=path)
                except obj.files.model.DoesNotExist:
                    file = None

            # get or create the entry_point
            now = datetime.utcnow()
            self.entry_point, created = getattr(obj, self.entry_point_related_name)\
                .get_or_create(**{
                    self.sha_field: sha,
                    'path': path,
                    self.position_field: position,
                    'defaults': {
                        'repository': obj.repository,
                        'commit_sha': sha,
                        'position': position,
                        'created_at': now,
                        'updated_at': now,
                        'diff_hunk': self.get_diff_hunk(file, position)
                    }
                })

    def post(self, *args, **kwargs):
        self.entry_point = None
        try:
            self.get_entry_point()
        except Exception:
            return self.http_method_not_allowed(self.request)
        return super(CommentWithEntryPointCreateViewMixin, self).post(*args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super(CommentWithEntryPointCreateViewMixin, self).get_form_kwargs()
        kwargs['entry_point'] = self.entry_point
        return kwargs


class PullRequestCommentCreateView(PullRequestCommentEditMixin, CommentWithEntryPointCreateViewMixin):
    url_name = 'issue.pr_comment.create'
    form_class = PullRequestCommentCreateForm

    null_path_allowed = False
    sha_field = 'original_commit_sha'
    position_field = 'original_position'
    entry_point_related_name = 'pr_comments_entry_points'

    @property
    def parent_object(self):
        return self.issue


class CommitCommentCreateView(CommitCommentEditMixin, CommentWithEntryPointCreateViewMixin):
    url_name = 'issue.commit_comment.create'
    form_class = CommitCommentCreateForm

    null_path_allowed = True
    sha_field = 'commit_sha'
    position_field = 'position'
    entry_point_related_name = 'commit_comments_entry_points'

    @property
    def parent_object(self):
        return self.commit

    def get_entry_point(self):
        return super(CommitCommentCreateView, self).get_entry_point(self.commit.sha)

    def get_success_url(self):
        url = super(CommitCommentCreateView, self).get_success_url()
        return url + '?include_form=1'


class CommentCheckRightsMixin(object):

    def get_object(self, queryset=None):
        """
        Early check that the user has enough rights to edit this comment
        """
        obj = super(CommentCheckRightsMixin, self).get_object(queryset)
        if self.subscription.state not in SUBSCRIPTION_STATES.WRITE_RIGHTS:
            if obj.user != self.request.user:
                raise Http404
        return obj


class BaseCommentEditView(CommentCheckRightsMixin, BaseCommentEditMixin, UpdateView):
    edit_mode = 'update'
    verb = 'updated'
    context_object_name = 'comment'
    pk_url_kwarg = 'comment_pk'
    template_name = 'front/repository/issues/comments/include_comment_edit.html'


class IssueCommentEditView(IssueCommentEditMixin, BaseCommentEditView):
    url_name = 'issue.comment.edit'
    form_class = IssueCommentEditForm


class PullRequestCommentEditView(PullRequestCommentEditMixin, BaseCommentEditView):
    url_name = 'issue.pr_comment.edit'
    form_class = PullRequestCommentEditForm


class CommitCommentEditView(CommitCommentEditMixin, BaseCommentEditView):
    url_name = 'issue.commit_comment.edit'
    form_class = CommitCommentEditForm


class BaseCommentDeleteView(BaseCommentEditView):
    edit_mode = 'delete'
    verb = 'deleted'
    template_name = 'front/repository/issues/comments/include_comment_delete.html'


class IssueCommentDeleteView(IssueCommentEditMixin, BaseCommentDeleteView):
    url_name = 'issue.comment.delete'
    form_class = IssueCommentDeleteForm


class PullRequestCommentDeleteView(PullRequestCommentEditMixin, BaseCommentDeleteView):
    url_name = 'issue.pr_comment.delete'
    form_class = PullRequestCommentDeleteForm


class CommitCommentDeleteView(CommitCommentEditMixin, BaseCommentDeleteView):
    url_name = 'issue.commit_comment.delete'
    form_class = CommitCommentDeleteForm
