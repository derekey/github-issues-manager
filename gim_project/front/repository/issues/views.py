from datetime import datetime
from math import ceil

from django.core.urlresolvers import reverse_lazy
from django.utils.datastructures import SortedDict
from django.db import DatabaseError
from django.views.generic import UpdateView, CreateView
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.http import Http404

from core.models import (Issue, GithubUser, LabelType, Milestone,
                         PullRequestCommentEntryPoint, IssueComment,
                         PullRequestComment)
from core.tasks.issue import IssueEditStateJob
from core.tasks.comment import IssueCommentEditJob, PullRequestCommentEditJob

from subscriptions.models import SUBSCRIPTION_STATES

from front.models import GroupedCommits
from front.views import LinkedToUserFormView
from ..views import BaseRepositoryView, LinkedToRepositoryFormView
from ...utils import make_querystring
from .forms import (IssueStateForm,
                    IssueCommentCreateForm, PullRequestCommentCreateForm)


class IssuesView(BaseRepositoryView):
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

    def get_usernames(self, relation):
        qs = getattr(self.repository, relation).order_by()
        return sorted(qs.values_list('username', flat=True), key=unicode.lower)

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
            'issues_creators': self.get_usernames('issues_creators'),
            'issues_assigned': self.get_usernames('issues_assigned'),
            'issues_closers': self.get_usernames('issues_closers'),
            'no_assigned_filter_url': self.repository.get_issues_user_filter_url_for_username('assigned', 'none'),
            'someone_assigned_filter_url': self.repository.get_issues_user_filter_url_for_username('assigned', '*'),
            'qs_parts_for_ttags': issues_filter['parts'],
            'label_types': label_types,
        })
        context['issues'] = self.finalize_issues(issues, context)

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
        issues_count = issues.count()

        if not issues_count:
            return []

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

        return issues


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

    def get_current_issue_for_context(self, context):
        """
        Based on the informations from the context and url, try to return
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
            current_issue = self.get_current_issue_for_context(context)
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
            context['current_issue'] = self.get_current_issue_for_context(context)
        except Issue.DoesNotExist:
            raise Http404

        return context


class FilesAjaxIssueView(SimpleAjaxIssueView):
    """
    Override SimpleAjaxIssueView to add comments in files (entry points)
    """
    ajax_template_name = 'front/repository/issues/include_issue_files.html'

    def get_context_data(self, **kwargs):
        context = super(FilesAjaxIssueView, self).get_context_data(**kwargs)
        context['entry_points_dict'] = self.get_entry_points_dict(context['current_issue'])
        return context


class BaseIssueEditView(LinkedToRepositoryFormView):
    model = Issue
    allowed_rights = SUBSCRIPTION_STATES.WRITE_RIGHTS
    http_method_names = [u'post']
    ajax_only = True

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        return queryset.get(number=self.kwargs['issue_number'])

    def get_success_url(self):
        return self.object.get_absolute_url()


class IssueEditState(LinkedToUserFormView, BaseIssueEditView, UpdateView):
    url_name = 'issue.edit.state'
    form_class = IssueStateForm

    def form_valid(self, form):
        """
        Override the default behavior to add a job to update the issue on the
        github side
        """
        response = super(IssueEditState, self).form_valid(form)

        new_state = form.cleaned_data['state']

        action = 'open' if new_state == 'open' else 'close'

        IssueEditStateJob.add_job(self.object.pk,
                                  gh=self.request.user.get_connection(),
                                  action=action)

        messages.success(self.request,
            u'The %s <strong>#%d</strong> will be %s shortly' % (
                    self.object.type, self.object.number,
                    'reopened' if new_state == 'open' else 'closed'))

        return response


class LinkedToIssueFormView(object):
    issue_related_name = 'issue'
    allowed_rights = SUBSCRIPTION_STATES.READ_RIGHTS  # everybody can add an issue
    ajax_only = False

    def get_issue_kwargs(self):
        return {
            'repository__owner__username': self.kwargs.get('owner_username', None),
            'repository__name': self.kwargs.get('repository_name', None),
            'number': self.kwargs.get('issue_number', None),
        }

    def dispatch(self, *args, **kwargs):
        filters = {
            'repository__subscriptions__user': self.request.user
        }
        if self.allowed_rights != SUBSCRIPTION_STATES.ALL_RIGHTS:
            filters['repository__subscriptions__state__in'] = self.allowed_rights

        queryset = Issue.objects.filter(**filters)

        issue_kwargs = self.get_issue_kwargs()
        self.issue = get_object_or_404(queryset, **issue_kwargs)

        return super(LinkedToIssueFormView, self).dispatch(*args, **kwargs)

    def get_queryset(self):
        return self.model._default_manager.filter(**{
                self.issue_related_name: self.issue
            })

    def post(self, *args, **kwargs):
        if self.ajax_only and not self.request.is_ajax():
            return self.http_method_not_allowed(self.request)
        return super(LinkedToIssueFormView, self).post(*args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super(LinkedToIssueFormView, self).get_form_kwargs()
        kwargs['issue'] = self.issue
        return kwargs


class BaseCommentCreateView(LinkedToUserFormView, LinkedToIssueFormView, CreateView):
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
