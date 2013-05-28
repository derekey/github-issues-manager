

def make_querystring(qs_parts):
    """
    Based on the given dict, generate a querystring, using keys of the dict as
    keys for the querystring, and values as values, but if the value is a list,
    join items by a comma
    """
    parts = []
    for key, value in qs_parts.items():
        if isinstance(value, list):
            parts.append((key, ','.join(value)))
        else:
            parts.append((key, value))

    qs = '&'.join('%s=%s' % part for part in parts)

    return '?' + qs
