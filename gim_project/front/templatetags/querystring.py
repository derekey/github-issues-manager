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
    qs = context.get('qs_parts_for_ttags', context.get('querystring_parts', None))
    return deepcopy(qs) if qs else {}


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
def toggle_one_from_querystring(context, key, value, remove_values=None):
    """
    {% toggle_one_in_querystring "label" "foo" %}
        => remove foo from labels if present, or add it if not
    {% toggle_one_in_querystring "label" "foo" remove_values=somelist %}
        => remove foo from labels if present, or add it if not, and remove
           all values from remove_values, except the the one defined as value
    """
    qs_parts = _get_qs_parts_from_context(context)
    value = _coerce_value(value)

    if value is not None:
        _set_part_as_list(qs_parts, key)
        if value in qs_parts[key]:
            qs_parts[key].remove(value)
        else:
            qs_parts[key].append(value)

    if remove_values:
        for val in remove_values:
            if val != value:
                try:
                    qs_parts[key].remove(val)
                except ValueError:
                    pass

    if not len(qs_parts[key]):
        del qs_parts[key]
    return make_querystring(qs_parts)
