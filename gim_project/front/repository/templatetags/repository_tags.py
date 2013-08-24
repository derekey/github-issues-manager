from django import template

from subscriptions.models import Subscription, SUBSCRIPTION_STATES

register = template.Library()


@register.filter
def repository_view_url(repository, url_name):
    return repository.get_view_url(url_name)


@register.filter
def can_user_write(repository, user):
    """
    Return True if the given user has write rights on the given repository
    """
    try:
        subscription = repository.subscriptions.get(user=user)
    except Subscription.DoesNotExist:
        return False
    else:
        return subscription.state in SUBSCRIPTION_STATES.WRITE
