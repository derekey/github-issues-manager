# -*- coding: utf-8 -*-

from datetime import datetime
import json
from math import ceil
from time import sleep

from django.core.urlresolvers import reverse_lazy
from django.utils.datastructures import SortedDict
from django.db import DatabaseError
from django.views.generic import UpdateView, CreateView, TemplateView
from django.contrib import messages
from django.shortcuts import render
from django.http import Http404, HttpResponseRedirect, HttpResponsePermanentRedirect

from limpyd_jobs import STATUSES

from core.models import (Issue, GithubUser, LabelType, Milestone,
                         PullRequestCommentEntryPoint, IssueComment,
                         PullRequestComment)
from core.tasks.issue import (IssueEditStateJob, IssueEditTitleJob,
                              IssueEditBodyJob, IssueEditMilestoneJob,
                              IssueEditAssigneeJob, IssueEditLabelsJob,
                              IssueCreateJob, FetchIssueByNumber)
from core.tasks.comment import IssueCommentEditJob, PullRequestCommentEditJob

from subscriptions.models import SUBSCRIPTION_STATES

from front.mixins.views import (WithQueryStringViewMixin,
                                LinkedToRepositoryFormViewMixin,
                                LinkedToIssueFormViewMixin,
                                LinkedToUserFormViewMixin,
                                DeferrableViewPart,
                                WithSubscribedRepositoryViewMixin,
                                WithAjaxRestrictionViewMixin)

from front.models import GroupedCommits
from front.repository.views import BaseRepositoryView

from front.utils import make_querystring
from .forms import (IssueStateForm, IssueTitleForm, IssueBodyForm,
                    IssueMilestoneForm, IssueAssigneeForm, IssueLabelsForm,
                    IssueCreateForm, IssueCreateFormFull,
                    IssueCommentCreateForm, PullRequestCommentCreateForm)

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
            'no_assigned_filter_url': self.repository.get_issues_user_filter_url_for_username('assigned', 'none'),
            'someone_assigned_filter_url': self.repository.get_issues_user_filter_url_for_username('assigned', '*'),
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
                       'group_by', 'group_by_direction', 'pr']
    allowed_states = ['open', 'closed']
    allowed_prs = ['no', 'yes']
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

    def _get_milestone(self, qs_parts):
        """
        Return the valid milestone to use, or None.
        A valid milestone can be "none" or a real Milestone object, based on a
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
            elif milestone_number == 'none':
                return 'none'
        return None

    def _get_labels(self, qs_parts):
        """
        Return the list of valid labels to use. The result is a list of Label
        objects, based on names found on the querystring
        """
        label_names = qs_parts.get('labels', None)
        if not label_names:
            return None
        if not isinstance(label_names, list):
            label_names = [label_names]
        label_names = [l for l in label_names if l]
        if len(label_names) == 1 and label_names[0] == 'none':
            return label_names
        return list(self.repository.labels.ready().filter(name__in=label_names))

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

        # filter by milestone
        milestone = self._get_milestone(qs_parts)
        if milestone is not None:
            filter_objects['milestone'] = milestone
            if milestone == 'none':
                qs_filters['milestone'] = 'none'
                query_filters['milestone__isnull'] = True
            else:
                qs_filters['milestone'] = '%s' % milestone.number
                query_filters['milestone__number'] = milestone.number

        # the base queryset with the current filters
        queryset = self.repository.issues.ready().filter(**query_filters)

        # now filter by labels
        labels = self._get_labels(qs_parts)
        if labels:
            filter_objects['labels'] = labels
            filter_objects['current_label_types'] = {}
            filter_objects['current_labels'] = []
            qs_filters['labels'] = []
            if len(labels) == 1 and labels[0] == 'none':
                label = labels[0]
                qs_filters['labels'].append(label)
                filter_objects['current_labels'].append(label)
                queryset = queryset.filter(labels__isnull=True)
            else:
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
            'no_assigned_filter_url': self.repository.get_issues_user_filter_url_for_username('assigned', 'none'),
            'someone_assigned_filter_url': self.repository.get_issues_user_filter_url_for_username('assigned', '*'),
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
        can be either the string "none", or a GithubUser object
        """
        filter_type = self.kwargs.get('user_filter_type', qs_parts.get('user_filter_type', None))
        username = self.kwargs.get('username', qs_parts.get('username', None))

        if username and filter_type in self.user_filter_types:
            if username == 'none':
                return filter_type, 'none'
            elif username == '*' and filter_type == 'assigned':
                return filter_type, '*'
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
            if user == 'none':
                queryset = queryset.filter(**{'%s__isnull' % filter_field: True})
            elif user == '*' and user_filter_type == 'assigned':
                queryset = queryset.filter(**{'%s__isnull' % filter_field: False})
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
        edit_level = None
        if current_issue:
            context['collaborators_ids'] = self.repository.collaborators.all().values_list('id', flat=True)
            activity = current_issue.get_activity()
            involved = self.get_involved_people(current_issue, activity, context['collaborators_ids'])
            if current_issue.number:
                if self.subscription.state in SUBSCRIPTION_STATES.WRITE_RIGHTS:
                    edit_level = 'full'
                elif self.subscription.state == SUBSCRIPTION_STATES.READ\
                                        and current_issue.user == self.request.user:
                    edit_level = 'self'

            if current_issue.is_pull_request:
                context['entry_points_dict'] = self.get_entry_points_dict(current_issue)

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

    def get_entry_points_dict(self, issue):
        """
        Return a dict that will be used in the issue files template to display
        pull request comments (entry points).
        The first level of the dict contains path of the file with entry points.
        The second level contains the position of the entry point, with the
        PullRequestCommentEntryPoint object as value
        """
        entry_points_dict = {}
        for entry_point in issue.all_entry_points:
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
                existing_users = job.users_to_inform.lmembers()
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
            if wait_if_failure:
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


class SimpleAjaxIssueView(IssueView):
    """
    A base class to fetch some parts of an issue via ajax.
    If not directly overriden, the template must be specified when using this
    view in urls.py
    """
    def dispatch(self, *args, **kwargs):
        """
        Accept only ajax
        """
        if not self.request.is_ajax():
            return self.http_method_not_allowed(self.request)
        return super(SimpleAjaxIssueView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        """
        Add the issue and its files in the context
        """
        # we bypass all the context stuff done by IssuesView by calling
        # directly its baseclass
        context = super(IssuesView, self).get_context_data(**kwargs)

        try:
            context['current_issue'] = self.get_current_issue()
        except Issue.DoesNotExist:
            raise Http404

        return context


class FilesAjaxIssueView(SimpleAjaxIssueView):
    """
    Override SimpleAjaxIssueView to add comments in files (entry points)
    """
    ajax_template_name = 'front/repository/issues/code/include_issue_files.html'

    def get_context_data(self, **kwargs):
        context = super(FilesAjaxIssueView, self).get_context_data(**kwargs)
        context['entry_points_dict'] = self.get_entry_points_dict(context['current_issue'])
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


class BaseCommentCreateView(LinkedToUserFormViewMixin, LinkedToIssueFormViewMixin, CreateView):
    job_model = None

    def get_success_url(self):
        return self.issue.get_absolute_url()

    def form_valid(self, form):
        """
        Override the default behavior to add a job to create the comment on the
        github side
        """
        response = super(BaseCommentCreateView, self).form_valid(form)

        self.job_model.add_job(self.object.pk,
                               mode='create',
                               gh=self.request.user.get_connection())

        messages.success(self.request,
            u'Your comment on the %s <strong>#%d</strong> will be created shortly' % (
                                            self.issue.type, self.issue.number))

        return response


class IssueCommentCreate(BaseCommentCreateView):
    url_name = 'issue.comment.create'
    form_class = IssueCommentCreateForm
    model = IssueComment
    job_model = IssueCommentEditJob


class PullRequestCommentCreate(BaseCommentCreateView):
    url_name = 'issue.pr_comment.create'
    form_class = PullRequestCommentCreateForm
    model = PullRequestComment
    job_model = PullRequestCommentEditJob

    def get_entry_point(self):
        if 'entry_point_id' in self.request.POST:
            entry_point_id = self.request.POST['entry_point_id']
            self.entry_point = self.issue.pr_comments_entry_points.get(id=entry_point_id)
        else:
            # get and check entre-point params

            if len(self.request.POST['position']) < 10:
                position = int(self.request.POST['position'])
            else:
                raise KeyError('position')

            if len(self.request.POST['sha']) == 40:
                sha = self.request.POST['sha']
            else:
                raise KeyError('sha')

            path = self.request.POST['path']
            try:
                file = self.issue.files.get(path=path)
            except self.issue.files.model.DoesNotExist:
                file = None

            # get or create the entry_point
            now = datetime.utcnow()
            self.entry_point, created = self.issue.pr_comments_entry_points\
                .get_or_create(
                    original_commit_sha=sha,
                    path=path,
                    original_position=position,
                    defaults={
                        'repository': self.issue.repository,
                        'commit_sha': sha,
                        'position': position,
                        'created_at': now,
                        'updated_at': now,
                        'diff_hunk': '' if not file else '\n'.join(
                                            file.patch.split('\n')[:position+1])
                    }
                )

    def post(self, *args, **kwargs):
        self.entry_point = None
        try:
            self.get_entry_point()
        except Exception:
            return self.http_method_not_allowed(self.request)
        return super(PullRequestCommentCreate, self).post(*args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super(PullRequestCommentCreate, self).get_form_kwargs()
        kwargs['entry_point'] = self.entry_point
        return kwargs
