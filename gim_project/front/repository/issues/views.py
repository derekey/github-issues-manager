from django.db.models import Q
from django.core.urlresolvers import reverse_lazy

from core.models import Issue, GithubUser, LabelType

from ..views import BaseRepositoryView
from ...utils import make_querystring


class IssuesView(BaseRepositoryView):
    name = 'Issues'
    url_name = 'issues'
    template_name = 'front/repository/issues/base.html'
    default_qs = 'state=open'

    allowed_filters = ['milestone', 'state', 'labels', 'sort', 'direction', 'group_by']
    allowed_states = ['open', 'closed']
    allowed_sort_fields = ['created', 'updated']
    allowed_sort_orders = ['asc', 'desc']
    allowed_group_by_fields = ['state', 'creator', 'assigned', 'milestone']
    default_sort = ('created', 'desc')

    def get_issues_for_context(self, context):
        """
        Read the querystring from the context, already cut in parts,
        and check parts that can be applied to filter issues, and return
        an issues queryset ready to use
        """
        repository = context['current_repository']
        qs_parts = self.get_qs_parts(context)

        filters = {}

        # filter by state
        qs_state = qs_parts.get('state', None)
        if qs_state in self.allowed_states:
            filters['state'] = qs_state

        # filter by milestone
        qs_milestone = qs_parts.get('milestone', None)
        if qs_milestone and not isinstance(qs_milestone, list):
            if qs_milestone.isdigit():
                filters['milestone__number'] = qs_parts['milestone']
            elif qs_milestone == 'none':
                filters['milestone__isnull'] = True

        # the base queryset with the current filter
        queryset = repository.issues.filter(**filters).prefetch_related('labels__label_type')

        # now filter by labels
        qs_labels = qs_parts.get('labels', None)
        if qs_labels:
            if not isinstance(qs_labels, list):
                qs_labels = [qs_labels]
            label_ids = repository.labels.filter(name__in=qs_labels).values_list('id', flat=True)
            Qs = []
            for label_id in label_ids:
                Qs.append(Q(labels=label_id))
            if len(Qs):
                queryset = queryset.filter(*Qs)

        # prepare order, by group then asked ordering
        order_by = []

        # do we need to group by a field ?
        qs_group_by = qs_parts.get('group_by', None)
        group_by_field = None
        if qs_group_by in self.allowed_group_by_fields:

            # group by a simple field
            group_by_field = {'creator': 'user', 'assigned': 'assignee'}.get(qs_group_by, qs_group_by)
            order_by.append(group_by_field)

        elif qs_group_by and qs_group_by.startswith('type:'):

            # group by a label type
            label_type_name = qs_group_by[5:]
            try:
                label_type = repository.label_types.get(name=label_type_name)
            except LabelType.DoesNotExist:
                pass
            else:
                context['group_by_label_type'] = label_type
                group_by_field = 'label_type_grouper'

        if group_by_field:
            # add the real field in context, to use by the "regroup" templatetag
            context['group_by_field'] = group_by_field

        # and finally, asked ordering
        qs_sort_field = qs_parts.get('sort', None)
        qs_sort_order = qs_parts.get('direction', None)
        if qs_sort_field not in self.allowed_sort_fields or qs_sort_order not in self.allowed_sort_orders:
            qs_sort_field, qs_sort_order = self.default_sort
        order_by.append('%s%s_at' % ('-' if qs_sort_order == 'desc' else '', qs_sort_field))

        # final order by, with group and wanted order
        queryset = queryset.order_by(*order_by)

        # add sort in context
        if 'querystring_parts' not in context:
            context['querystring_parts'] = {}
        context['querystring_parts'].update({
            'sort': qs_sort_field,
            'direction': qs_sort_order,
        })
        # set the group_by_field if ok, else remove it
        if group_by_field:
            context['group_by_field'] = group_by_field
        else:
            context['querystring_parts'].pop('group_by', None)

        return queryset

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
        issues = self.get_issues_for_context(context)

        # get the whole issue filter
        issues_filter = {}
        # querystring parts
        qs_parts = self.get_qs_parts(context)
        issue_filter_parts = {}
        for part in qs_parts:
            if part in self.allowed_filters:
                issue_filter_parts[part] = qs_parts[part]
        if issue_filter_parts:
            issues_filter.update({
                'querystring': make_querystring(issue_filter_parts),
                'parts': issue_filter_parts,
            })
        # user parts
        issue_user_filter_parts = {}
        user_filter_type = self.kwargs.get('user_filter_type', qs_parts.get('user_filter_type', None))
        username = self.kwargs.get('username', qs_parts.get('username', None))
        if user_filter_type and username:
            issue_user_filter_parts.update(issue_filter_parts)
            issue_user_filter_parts.update({
                'user_filter_type': user_filter_type,
                'username': username,
            })
            issues_filter['parts'].update(issue_user_filter_parts)
            issues_filter.update({
                'querystring_with_user_filter': make_querystring(issue_user_filter_parts),
            })

        # final context
        issues_url = reverse_lazy('front:repository:%s' % IssuesView.url_name,
                                  kwargs=repository.get_reverse_kwargs())
        context.update({
            'root_issues_url': issues_url,
            'current_issues_url': issues_url,
            'issues_filter': issues_filter,
            'collaborators': users_lists['collaborators'],
            'issues_creators': users_lists['issues_creators'],
            'no_assigned_filter_url': repository.get_issues_user_filter_url_for_username('assigned', 'none'),
        })
        context['issues'] = self.finalize_issues(issues, context)

        return context

    def finalize_issues(self, issues, context):
        """
        Return a final list of issues usable in the view.
        Actually simply order ("group") by a label_type if asked
        """
        if not issues:
            return issues

        if context.get('group_by_label_type', None) and context.get('group_by_field', None):
            attribute = context['group_by_field']
            label_type = context['group_by_label_type']

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
            for label in [None] + list(label_type.labels.all()):
                label_id = None if label is None else label.id
                if label_id in issues_dict:
                    issues += issues_dict[label_id]

        return issues


class UserIssuesView(IssuesView):
    url_name = 'user_issues'
    user_filter_types = ['assigned', 'created', ]
    allowed_filters = IssuesView.allowed_filters + user_filter_types

    def get_issues_for_context(self, context):
        """
        Update the previously done queryset by filtering by a user as assigned
        to issues, or their creator
        """
        queryset = super(UserIssuesView, self).get_issues_for_context(context)
        qs_parts = self.get_qs_parts(context)

        user_filter_type = self.kwargs.get('user_filter_type', qs_parts.get('user_filter_type', None))
        username = self.kwargs.get('username', qs_parts.get('username', None))

        if username and user_filter_type in self.user_filter_types:
            do_filter = True

            if username != 'none':
                try:
                    user = GithubUser.objects.get(username=username)
                except GithubUser.DoesNotExist:
                    do_filter = False

            if do_filter:
                filter_field = 'user' if user_filter_type == 'created' else 'assignee'
                if username == 'none':
                    queryset = queryset.filter(**{'%s__isnull' % filter_field: True})
                else:
                    queryset = queryset.filter(**{filter_field: user.id})

                context.update({
                    'current_%s' % user_filter_type: username,
                    'user_filter_type': user_filter_type,
                    'user_filter_username': username,
                })

        return queryset

    def get_context_data(self, **kwargs):
        """
        Set the current base url for issues for this view
        """
        context = super(UserIssuesView, self).get_context_data(**kwargs)
        repository = context['current_repository']

        if 'user_filter_type' in context and 'user_filter_username' in context:
            current_issues_url_kwargs = repository.get_reverse_kwargs()
            current_issues_url_kwargs.update({
                'user_filter_type': context['user_filter_type'],
                'username': context['user_filter_username'],
            })
            context['current_issues_url'] = reverse_lazy(
                                    'front:repository:%s' % UserIssuesView.url_name,
                                    kwargs=current_issues_url_kwargs)

        # remove user filter fields we don't want to be managed in other filters toggling
        if 'querystring_parts' in context:
            context['querystring_parts'].pop('user_filter_type', None)
            context['querystring_parts'].pop('username', None)

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
