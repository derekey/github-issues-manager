from django import template

register = template.Library()


def _base_url_issues_for_user(repository, user, filter_type):
    if filter_type not in ('created', 'assigned'):
        return ''
    return repository.get_issues_user_filter_url_for_username(filter_type, user.username if user else "none")


@register.filter
def base_url_issues_filtered_by_created(repository, user):
    return _base_url_issues_for_user(repository, user, 'created')


@register.filter
def base_url_issues_filtered_by_assigned(repository, user):
    return _base_url_issues_for_user(repository, user, 'assigned')
