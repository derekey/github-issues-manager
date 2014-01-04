# -*-coding: utf8 -*-

"""
dynamic_group comes from http://djangosnippets.org/snippets/2511/
"""
from itertools import groupby, chain
from datetime import datetime
import time
import re
import whatthepatch

from pytimeago.english import english as english_ago
from pytimeago.english_short import english_short as english_short_ago

from django import template
from django.template import TemplateSyntaxError

register = template.Library()


class DynamicRegroupNode(template.Node):
    def __init__(self, target, parser, expression, var_name):
        self.target = target
        self.expression = template.Variable(expression)
        self.var_name = var_name
        self.parser = parser

    def render(self, context):
        obj_list = self.target.resolve(context, True)
        if obj_list is None:
            # target variable wasn't found in context; fail silently.
            context[self.var_name] = []
            return ''
        # List of dictionaries in the format:
        # {'grouper': 'key', 'list': [list of contents]}.

        """
        Try to resolve the filter expression from the template context.
        If the variable doesn't exist, accept the value that passed to the
        template tag and convert it to a string
        """
        try:
            exp = self.expression.resolve(context)
        except template.VariableDoesNotExist:
            exp = str(self.expression)

        filter_exp = self.parser.compile_filter(exp)

        context[self.var_name] = [
            {'grouper': key, 'list': list(val)}
            for key, val in
            groupby(obj_list, lambda v, f=filter_exp.resolve: f(v, True))
        ]

        return ''


@register.tag
def dynamic_regroup(parser, token):
    firstbits = token.contents.split(None, 3)
    if len(firstbits) != 4:
        raise TemplateSyntaxError("'regroup' tag takes five arguments")
    target = parser.compile_filter(firstbits[1])
    if firstbits[2] != 'by':
        raise TemplateSyntaxError("second argument to 'regroup' tag must be 'by'")
    lastbits_reversed = firstbits[3][::-1].split(None, 2)
    if lastbits_reversed[1][::-1] != 'as':
        raise TemplateSyntaxError("next-to-last argument to 'regroup' tag must"
                                  " be 'as'")

    """
    Django expects the value of `expression` to be an attribute available on
    your objects. The value you pass to the template tag gets converted into a
    FilterExpression object from the literal.

    Sometimes we need the attribute to group on to be dynamic. So, instead
    of converting the value to a FilterExpression here, we're going to pass the
    value as-is and convert it in the Node.
    """
    expression = lastbits_reversed[2][::-1]
    var_name = lastbits_reversed[0][::-1]

    """
    We also need to hand the parser to the node in order to convert the value
    for `expression` to a FilterExpression.
    """
    return DynamicRegroupNode(target, parser, expression, var_name)


@register.assignment_tag(takes_context=True)
def attributes_for_list(context, items, attribute, none_if_missing=False):
    """
    Take a list of items (or something that can be iterated) and for each one,
    return the given attribute, in a list. If the attribute is not found for an
    item, no entry for this item will be returned, except if none_if_missing is
    True, in which case None will be returned.
    """
    if not items:
        return []
    final_list = []
    for item in items:
        if isinstance(item, dict):
            if none_if_missing or attribute in item:
                final_list.append(item.get(attribute, None))
        else:
            if none_if_missing or hasattr(item, attribute):
                final_list.append(getattr(item, attribute, None))
    return final_list


@register.filter
def dict_item(dikt, key):
    """
Custom template tag used like so:
{{ dictionary|dict_item:var }}
where dictionary is a dictionary and key is a variable representing
one of it's keys
"""
    try:
        return dikt.__getitem__(key)
    except:
        return ''


@register.filter
def attr(obj, attr):
    """
Custom template tag used like so:
{{ object|attr:var }}
where object is an object with attributes and attr is a variable representing
one of it's attributes
"""
    try:
        result = getattr(obj, attr)
        if callable(result):
            return result()
        return result
    except:
        return ''


@register.filter
def ago(date, short=False):
    method = english_short_ago if short else english_ago
    try:
        return method(time.mktime(datetime.now().timetuple()) - time.mktime(date.timetuple()))
    except:
        return ''

register.filter('ago', ago)


class NoSpacesNode(template.Node):
    """
    """
    spaces = re.compile('\s')

    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        return self.spaces.sub('', self.nodelist.render(context).strip())


@register.tag
def nospaces(parser, token):
    """
    Removes all spaces in the templatetag

    Example usage::

        <div class="{% nospaces %}
            {% if foo %}
                foo
            {% else %}
                bar
            {% endif %}
        {% endnospaces %}">


    This example would return this HTML::

        <div class="foo">
    """
    nodelist = parser.parse(('endnospaces',))
    parser.delete_first_token()
    return NoSpacesNode(nodelist)


@register.filter
def tolist(value):
    return [value]


DIFF_LINE_TYPES = {
    '@': 'comment',
    '+': 'added',
    '-': 'removed',
    ' ': '',
}


@register.filter
def parse_diff(diff, reduce=False):
    if not diff or not diff.startswith('@@'):
        return []

    # split hunks
    parts = []
    for l in diff.split('\n'):
        if l.startswith('@@'):
            parts.append([])
        parts[-1].append(l)

    results = []
    position = 0

    if reduce:
        parts = parts[-1:]

    # parse each hunk
    for part in parts:
        diff = whatthepatch.parse_patch(part).next()  # only one file = only one diff
        result = [['comment', u'…', u'…', part[0], position]]
        for old, new, text in diff.changes:
            position += 1
            mode = ' ' if old and new else '-' if old else '+'
            result.append([
                DIFF_LINE_TYPES[mode],
                old or '',
                new or '',
                mode + text,
                position,
            ])
        position += 1
        if reduce:
            result = result[0:1] + result[1:][-12:]

        results.append(result)

    return chain.from_iterable(results)


@register.filter
def short_sha(sha, length=8):
    return sha[:length]


@register.simple_tag(takes_context=True)
def import_debug(context):
    import debug
    return ""
