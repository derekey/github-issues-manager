from django.db.models import Q
from django.core.urlresolvers import reverse_lazy

from core.models import Issue, GithubUser, LabelType, Milestone

from ..views import BaseRepositoryView
from ...utils import make_querystring


class IssuesView(BaseRepositoryView):
    name = 'Issues'
    url_name = 'issues'
    template_name = 'front/repository/issues/base.html'
    default_qs = 'state=open'

    allowed_filters = ['milestone', 'state', 'labels', 'sort', 'direction',
                       'group_by', 'group_by_direction']
    allowed_states = ['open', 'closed']
    allowed_sort_fields = ['created', 'updated']
    allowed_sort_orders = ['asc', 'desc']
    allowed_group_by_fields = ['state', 'creator', 'assigned', 'milestone']
    default_sort = ('created', 'desc')

    def _get_state(self, repository, qs_parts):
        """
        Return the valid state to use, or None
        """
        state = qs_parts.get('state', None)
        if state in self.allowed_states:
            return state
        return None

    def _get_milestone(self, repository, qs_parts):
        """
        Return the valid milestone to use, or None.
        A valid milestone can be "none" or a real Milestone object, based on a
        milestone number found in the querystring
        """
        milestone_number = qs_parts.get('milestone', None)
        if milestone_number and isinstance(milestone_number, basestring):
            if milestone_number.isdigit():
                try:
                    milestone = repository.milestones.get(number=milestone_number)
                except Milestone.DoesNotExist:
                    pass
                else:
                    return milestone
            elif milestone_number == 'none':
                return 'none'
        return None

    def _get_labels(self, repository, qs_parts):
        """
        Return the list of valid labels to use. The result is a list of Label
        objects, based on names found on the querystring
        """
        label_names = qs_parts.get('labels', None)
        if not label_names:
            return None
        if not isinstance(label_names, list):
            label_names = [label_names]
        return list(repository.labels.filter(name__in=label_names))

    def _get_group_by(self, repository, qs_parts):
        """
        Return the group_by field to use, and the direction.
        The group_by field can be either an allowed string, or an existing
        LabelType
        """
        group_by = qs_parts.get('group_by', None)

        if group_by in self.allowed_group_by_fields:

            # group by a simple field
            group_by = {'creator': 'user', 'assigned': 'assignee'}.get(group_by, group_by)

        elif group_by and group_by.startswith('type:'):

            # group by a label type
            label_type_name = group_by[5:]
            try:
                label_type = repository.label_types.get(name=label_type_name)
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

    def _get_sort(self, repository, qs_parts):
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
        repository = context['current_repository']
        qs_parts = self.get_qs_parts(context)

        qs_filters = {}
        filter_objects = {}

        query_filters = {}

        # filter by state
        state = self._get_state(repository, qs_parts)
        if state is not None:
            qs_filters['state'] = filter_objects['state'] = query_filters['state'] = state

        # filter by milestone
        milestone = self._get_milestone(repository, qs_parts)
        if milestone is not None:
            filter_objects['milestone'] = milestone
            if milestone == 'none':
                qs_filters['milestone'] = 'none'
                query_filters['milestone__isnull'] = True
            else:
                qs_filters['milestone'] = '%s' % milestone.number
                query_filters['milestone__number'] = milestone.number

        # the base queryset with the current filter
        queryset = repository.issues.filter(**query_filters).prefetch_related('labels__label_type')

        # now filter by labels
        labels = self._get_labels(repository, qs_parts)
        if labels:
            filter_objects['labels'] = labels
            qs_filters['labels'] = [l.name for l in labels]
            Q_objects = [Q(labels=label.id) for label in labels]
            if len(Q_objects):
                queryset = queryset.filter(*Q_objects)

        # prepare order, by group then asked ordering
        order_by = []

        # do we need to group by a field ?
        group_by, group_by_direction = self._get_group_by(repository, qs_parts)
        if group_by is not None:
            filter_objects['group_by'] = group_by
            filter_objects['group_by_direction'] = qs_filters['group_by_direction'] = group_by_direction
            if isinstance(group_by, basestring):
                qs_filters['group_by'] = group_by
                filter_objects['group_by_field'] = group_by
                order_by.append('%s%s' % ('-' if group_by_direction == 'desc' else '', group_by))
            else:
                qs_filters['group_by'] = 'type:%s' % group_by.name
                filter_objects['group_by_field'] = 'label_type_grouper'

        # and finally, asked ordering
        sort, sort_direction = self._get_sort(repository, qs_parts)
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
        repository = context['current_repository']

        # get the lists of people
        users_lists = {
            'collaborators': [],
            'issues_creators': [],
        }
        for filter_type, repo_field in (('created', 'issues_creators'), ('assigned', 'collaborators')):
            users = getattr(repository, repo_field).all()
            for user in users:
                url = repository.get_issues_user_filter_url_for_username(filter_type, user.username)
                setattr(user, '%s_filter_url' % filter_type, url)
                users_lists[repo_field].append(user)

        # get the list of issues
        issues, filter_context = self.get_issues_for_context(context)

        # final context
        issues_url = reverse_lazy('front:repository:%s' % IssuesView.url_name,
                                  kwargs=repository.get_reverse_kwargs())

        issues_filter = self.prepare_issues_filter_context(filter_context)
        context.update({
            'root_issues_url': issues_url,
            'current_issues_url': issues_url,
            'issues_filter': issues_filter,
            'collaborators': users_lists['collaborators'],
            'issues_creators': users_lists['issues_creators'],
            'no_assigned_filter_url': repository.get_issues_user_filter_url_for_username('assigned', 'none'),
            'qs_parts_for_ttags': issues_filter['parts']
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
        if not issues:
            return issues

        label_type = context['issues_filter']['objects'].get('group_by', None)
        attribute = context['issues_filter']['objects'].get('group_by_field', None)
        if label_type and isinstance(label_type, LabelType) and attribute:

            # regroup issues by label from the lab
            issues_dict = {}
            for issue in issues.all():
                add_to = None

                for label in issue.labels.all():  # thanks prefetch_related
                    if label.label_type_id == label_type.id:
                        # found a label for the wanted type, mark it and stop
                        # checking labels for this issue
                        add_to = label.id
                        setattr(issue, attribute, label.typed_name)
                        break

                # add in a dict, with one entry for each label of the type (and one for None)
                issues_dict.setdefault(add_to, []).append(issue)

            # for each label of the type, append matching issues to the final
            # list
            issues = []
            label_type_labels = [None] + list(label_type.labels.all())
            if context['issues_filter']['parts'].get('group_by_direction', 'asc') == 'desc':
                label_type_labels.reverse()
            for label in label_type_labels:
                label_id = None if label is None else label.id
                if label_id in issues_dict:
                    issues += issues_dict[label_id]

        return issues


class UserIssuesView(IssuesView):
    url_name = 'user_issues'
    user_filter_types = ['assigned', 'created', ]
    allowed_filters = IssuesView.allowed_filters + user_filter_types

    def _get_user_filter(self, repository, qs_parts):
        """
        Return the user filter type used, and the user to filter on. The user
        can be either the string "none", or a GithubUser object
        """
        filter_type = self.kwargs.get('user_filter_type', qs_parts.get('user_filter_type', None))
        username = self.kwargs.get('username', qs_parts.get('username', None))

        if username and filter_type in self.user_filter_types:
            if username == 'none':
                return filter_type, 'none'
            if username != 'none':
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
        to issues, or their creator
        """
        queryset, filter_context = super(UserIssuesView, self).get_issues_for_context(context)
        repository = context['current_repository']
        qs_parts = self.get_qs_parts(context)

        user_filter_type, user = self._get_user_filter(repository, qs_parts)
        if user_filter_type and user:
            filter_context['filter_objects']['user'] = user
            filter_context['filter_objects']['user_filter_type'] = user_filter_type
            filter_context['qs_filters']['user_filter_type'] = user_filter_type
            filter_field = 'user' if user_filter_type == 'created' else 'assignee'
            if user == 'none':
                filter_context['qs_filters']['username'] = user
                queryset = queryset.filter(**{'%s__isnull' % filter_field: True})
            else:
                filter_context['qs_filters']['username'] = user.username
                queryset = queryset.filter(**{filter_field: user.id})

        return queryset, filter_context

    def get_context_data(self, **kwargs):
        """
        Set the current base url for issues for this view
        """
        context = super(UserIssuesView, self).get_context_data(**kwargs)
        repository = context['current_repository']

        user_filter_type = context['issues_filter']['objects'].get('user_filter_type', None)
        user_filter_user = context['issues_filter']['objects'].get('user', None)
        if user_filter_type and user_filter_user:
            context['issues_filter']['objects']['current_%s' % user_filter_type] = context['issues_filter']['parts']['username']
            current_issues_url_kwargs = repository.get_reverse_kwargs()
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

    def get_current_issue_for_context(self, context):
        """
        Based on the informations from the context and url, try to return
        the wanted issue
        """
        issue = None
        if 'issue_number' in self.kwargs:
            repository = context['current_repository']
            issue = repository.issues.get(number=self.kwargs['issue_number'])
        return issue

    def get_context_data(self, **kwargs):
        """
        Add the selected view in the context
        """
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

        # final context
        context.update({
            'current_issue': current_issue,
            'current_issue_state': current_issue_state,
        })

        return context
