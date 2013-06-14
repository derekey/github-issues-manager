from django import template

register = template.Library()


@register.filter
def repository_view_url(repository, url_name):
    return repository.get_view_url(url_name)
