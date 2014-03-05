from django.conf.urls import patterns, url

from .views import (IssuesView, IssueView, UserIssuesView,
                    SimpleAjaxIssueView, FilesAjaxIssueView,
                    IssueEditState, IssueEditTitle, IssueEditBody,
                    IssueEditMilestone, IssueEditAssignee, IssueEditLabels,
                    IssueCommentCreate, PullRequestCommentCreate)

urlpatterns = patterns('',
    url(r'^$', IssuesView.as_view(), name=IssuesView.url_name),
    url(r'^(?P<user_filter_type>(?:assigned|created_by|closed_by))/(?P<username>[^/]+)/$', UserIssuesView.as_view(), name=UserIssuesView.url_name),
    url(r'^(?P<issue_number>\d+)/$', IssueView.as_view(), name=IssueView.url_name),

    # parts
    url(r'^(?P<issue_number>\d+)/files/$', FilesAjaxIssueView.as_view(), name='issue.files'),
    url(r'^(?P<issue_number>\d+)/commits/$', SimpleAjaxIssueView.as_view(ajax_template_name='front/repository/issues/include_issue_commits.html'), name='issue.commits'),

    # edit views
    url(r'^(?P<issue_number>\d+)/edit/state/$', IssueEditState.as_view(), name=IssueEditState.url_name),
    url(r'^(?P<issue_number>\d+)/edit/title/$', IssueEditTitle.as_view(), name=IssueEditTitle.url_name),
    url(r'^(?P<issue_number>\d+)/edit/body/$', IssueEditBody.as_view(), name=IssueEditBody.url_name),
    url(r'^(?P<issue_number>\d+)/edit/milestone/$', IssueEditMilestone.as_view(), name=IssueEditMilestone.url_name),
    url(r'^(?P<issue_number>\d+)/edit/assignee/$', IssueEditAssignee.as_view(), name=IssueEditAssignee.url_name),
    url(r'^(?P<issue_number>\d+)/edit/labels/$', IssueEditLabels.as_view(), name=IssueEditLabels.url_name),

    url(r'^(?P<issue_number>\d+)/comment/add/$', IssueCommentCreate.as_view(), name=IssueCommentCreate.url_name),
    url(r'^(?P<issue_number>\d+)/code-comment/add/$', PullRequestCommentCreate.as_view(), name=PullRequestCommentCreate.url_name),
)
