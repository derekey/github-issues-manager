from copy import deepcopy

from django import template

from ..utils import make_querystring

register = template.Library()


def _set_part_as_list(qs_parts, name):
    """
    Force the name entry of qs_parts to be a list.
    If it exists and it's not a list, set the content as the first element of
    the new list.
    """
    if name not in qs_parts:
        qs_parts[name] = []
    elif not isinstance(qs_parts[name], list):
        value = qs_parts[name]
        qs_parts[name] = []
        if value is not None:
            qs_parts[name] = [value]


def _coerce_value(value):
    """
    Force the value to be a string, or None
    """
    if value is None:
        return None
    return '%s' % value


def _get_qs_parts_from_context(context):
    """
    Return a deep copied version of the querystring_parts found in the context
    (or {} if not found)
    """
    return deepcopy(context['querystring_parts']) if 'querystring_parts' in context else {}


@register.simple_tag(takes_context=True)
def replace_in_querystring(context, key, value):
    """
    {% replace_in_querystring "state" "open" %}
        => set the state to open
    """
    qs_parts = _get_qs_parts_from_context(context)
    value = _coerce_value(value)
    if value is None:
        qs_parts.pop(key, None)
    else:
        qs_parts[key] = value
    return make_querystring(qs_parts)


@register.simple_tag(takes_context=True)
def replace_many_in_querystring(context, *args):
    """
    {% replace_many_in_querystring "sort" "created" "direction" "asc" %}
        => set the sort to created and the direction to asc
    """
    qs_parts = _get_qs_parts_from_context(context)
    pairs = zip(args[::2], args[1::2])
    for key, value in pairs:
        value = _coerce_value(value)
        if value is None:
            qs_parts.pop(key, None)
        else:
            qs_parts[key] = value
    return make_querystring(qs_parts)


@register.simple_tag(takes_context=True)
def toggle_in_querystring(context, key, value):
    """
    {% toggle_in_querystring "state" "open" %}
        => is state is open, remove the state, else set state to open
    """
    qs_parts = _get_qs_parts_from_context(context)
    value = _coerce_value(value)
    if value is not None:
        if key in qs_parts and qs_parts[key] == value:
            del qs_parts[key]
        else:
            qs_parts[key] = value
    return make_querystring(qs_parts)


@register.simple_tag(takes_context=True)
def add_to_querystring(context, key, value):
    """
    {% add_to_querystring "labels" "foo" %}
        => add foo to labels
    """
    qs_parts = _get_qs_parts_from_context(context)
    value = _coerce_value(value)
    _set_part_as_list(qs_parts, key)
    qs_parts[key].append(value)
    return make_querystring(qs_parts)


@register.simple_tag(takes_context=True)
def remove_from_querystring(context, key, value=None):
    """
    {% remove_from_querystring "labels" "foo" %}
        => remove foo from labels
    {% remove_from_querystring "labels" %}
        => remove the labels key
    """
    qs_parts = _get_qs_parts_from_context(context)
    value = _coerce_value(value)
    if value is None:
        qs_parts.pop(key)
    else:
        _set_part_as_list(qs_parts, key)
        try:
            qs_parts[key].remove(value)
        except ValueError:
            pass
        if not len(qs_parts[key]):
            del qs_parts[key]
    return make_querystring(qs_parts)


@register.simple_tag(takes_context=True)
def toggle_one_from_querystring(context, key, value):
    """
    {% toggle_one_in_querystring "label" "foo" %}
        => remove foo from labels if present, or add it if not
    """
    qs_parts = _get_qs_parts_from_context(context)
    value = _coerce_value(value)
    if value is not None:
        _set_part_as_list(qs_parts, key)
        if value in qs_parts[key]:
            qs_parts[key].remove(value)
            if not len(qs_parts[key]):
                del qs_parts[key]
        else:
            qs_parts[key].append(value)
    return make_querystring(qs_parts)


@register.simple_tag(takes_context=True)
def toggle_value_if_in_querystring(context, key, value, if_true, if_false=""):
    """
    {% toggle_value_if_in_querystring "labels" "foo" "active" "inactive" %}
        => display active if foo is in labels, inactive if not
    {% toggle_value_if_in_querystring "state" "open" "active" "inactive" %}
        => display active if state is open, inactive if not
    """
    qs_parts = _get_qs_parts_from_context(context)
    value = _coerce_value(value)
    if value is None or key not in qs_parts:
        return if_false
    if isinstance(qs_parts[key], list):
        return if_true if value in qs_parts[key] else if_false
    else:
        return if_true if value == qs_parts[key] else if_false


@register.simple_tag(takes_context=True)
def toggle_value_if_many_in_querystring(context, *args, **kwargs):
    """
    {% toggle_value_if_in_querystring "sort" "created" "direction" "asc" if_true="active" if_false="inactive" %}
        => display active if sort is created and direction is asc, else inactive
    """
    if_true = kwargs.get('if_true', '')
    if_false = kwargs.get('if_false', '')

    qs_parts = _get_qs_parts_from_context(context)

    pairs = zip(args[::2], args[1::2])
    found = True
    for key, value in pairs:
        value = _coerce_value(value)
        if value is None or key not in qs_parts:
            found = False
        else:
            if isinstance(qs_parts[key], list):
                found = value in qs_parts[key]
            else:
                found = value == qs_parts[key]
        if not found:
            break

    return if_true if found else if_false
