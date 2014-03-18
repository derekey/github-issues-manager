"""
BASED on http://www.minddust.com/post/django-spaceless-with-preserved-pre-formatting/
Copyright (c) 2013-2014 Stephan Gross, under MIT license.
"""
from __future__ import unicode_literals

import re

from django import template
from django.template import Node
from django.utils import six
from django.utils.encoding import force_text
from django.utils.functional import allow_lazy


register = template.Library()

RE_FIND_PRE = re.compile(r'<pre(?:\s[^>]*)?>(?:.*?)</pre>', flags=re.S | re.M | re.I)
RE_RESTORE_PRE = re.compile(r'%preplaceholder_(\d+)%')
RE_SPACES = re.compile(r'>\s+<')


def strip_spaces_between_tags_except_pre(value):
    matches = []

    def replacement(match):
        matches.append(match.group(0)[1:-1])  # save the whole match without leading "<" and trailing ">"
        return '<%%preplaceholder_%d%%>' % (len(matches) - 1)  # add "<" and ">" to preserve space stripping

    value = RE_FIND_PRE.sub(replacement, force_text(value))
    value = RE_SPACES.sub('><', force_text(value))
    return RE_RESTORE_PRE.sub(lambda match: matches[int(match.group(1))], value)
strip_spaces_between_tags_except_pre = allow_lazy(strip_spaces_between_tags_except_pre, six.text_type)


class SpacelessExceptPreNode(Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        return strip_spaces_between_tags_except_pre(self.nodelist.render(context).strip())


@register.tag
def spaceless_except_pre(parser, token):
    """Remove whitespace between HTML tags, including tab and newline characters except content between <pre>"""
    nodelist = parser.parse(('endspaceless_except_pre',))
    parser.delete_first_token()
    return SpacelessExceptPreNode(nodelist)
