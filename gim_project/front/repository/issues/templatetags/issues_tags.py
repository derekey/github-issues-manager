from django import template

from ..views import UserIssuesView

register = template.Library()


def _base_url_issues_for_user(repository, user, filter_type):
    if filter_type not in UserIssuesView.user_filter_types:
        return ''
    return repository.get_issues_user_filter_url_for_username(filter_type, user.username if user else "none")


@register.filter
def base_url_issues_filtered_by_created_by(repository, user):
    return _base_url_issues_for_user(repository, user, 'created_by')


@register.filter
def base_url_issues_filtered_by_assigned(repository, user):
    return _base_url_issues_for_user(repository, user, 'assigned')


@register.filter
def base_url_issues_filtered_by_closed_by(repository, user):
    return _base_url_issues_for_user(repository, user, 'closed_by')
