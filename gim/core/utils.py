import gc
from functools import wraps

from django.db import models


def contribute_to_model(contrib, destination):
    """
    Update ``contrib`` model based on ``destination``.

    Every new field will be created. Existing fields will have some properties
    updated.

    Methods and properties of ``contrib`` will populate ``destination``.

    Usage example:

    >>> from django.contrib.auth.models import User
    >>> from django.db import models
    >>>
    >>> class MyUser(models.Model):
    >>>     class Meta:
    >>>         abstract = True
    >>>         db_table = 'user' # new auth_user table name
    >>>
    >>>     # New field
    >>>     phone = models.CharField('phone number', blank=True, max_length=20)
    >>>
    >>>     # Email could be null
    >>>     email = models.EmailField(blank=True, null=True)
    >>>
    >>>     # New (stupid) method
    >>>     def get_phone(self):
    >>>         return self.phone
    >>>
    >>> contribute_to_model(MyUser, User)

    """

    # Contrib should be abstract
    if not contrib._meta.abstract:
        raise ValueError('Your contrib model should be abstract.')

    # Update or create new fields
    for field in contrib._meta.fields:
        try:
            destination._meta.get_field_by_name(field.name)
        except models.FieldDoesNotExist:
            field.contribute_to_class(destination, field.name)
        else:
            current_field = destination._meta.get_field_by_name(field.name)[0]
            current_field.null = field.null
            current_field.blank = field.blank
            current_field.max_length = field.max_length
            current_field._unique = field.unique

    # Change some meta information
    if hasattr(contrib.Meta, 'db_table'):
        destination._meta.db_table = contrib._meta.db_table

    # Add (or replace) properties and methods
    protected_items = dir(models.Model) + ['Meta', '_meta']
    for k, v in contrib.__dict__.items():
        if k not in protected_items:
            setattr(destination, k, v)


def queryset_iterator(queryset, chunksize=1000):
    '''
    Iterate over a Django Queryset ordered by the primary key

    This method loads a maximum of chunksize (default: 1000) rows in it's
    memory at the same time while django normally would load all rows in it's
    memory. Using the iterator() method only causes it to not preload all the
    classes.

    Note that the implementation of the iterator does not support ordered query sets.

    from http://www.mellowmorning.com/2010/03/03/django-query-set-iterator-for-really-large-querysets/
    '''
    pk = 0
    last_pk = queryset.order_by('-pk')[0].pk
    queryset = queryset.order_by('pk')
    while pk < last_pk:
        for row in queryset.filter(pk__gt=pk)[:chunksize]:
            pk = row.pk
            yield row
        gc.collect()


def cached_method(func):
    """
    Based on django.util.functional.memoize. Automatically memoizes instace methods for the lifespan
    of an object.
    Only works with methods taking non-keword arguments. Note that the args to the function must be
    usable as dictionary keys. Also, the first argument MUST be self. This decorator will not work
    for functions or class methods, only object methods.
    https://djangosnippets.org/snippets/2874/
    """
    @wraps(func)
    def wrapper(*args):
        inst = args[0]
        inst._memoized_values = getattr(inst, '_memoized_values', {})
        key = (func, args[1:])
        if key not in inst._memoized_values:
            inst._memoized_values[key] = func(*args)
        return inst._memoized_values[key]
    return wrapper
