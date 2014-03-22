"""
The goal of this hack is to avoid doing clear + add when updating m2m values.
The problem is that this generate "clear" then "add" m2m_changed signals and
so we are not able to track the updates.
"""
from django.db import router
from django.db.models.fields.related import (
    ManyRelatedObjectsDescriptor,
    ReverseManyRelatedObjectsDescriptor,
)


def m2m_replace(self, *new_objs):
    """
    A better alternative to the default behavior which is to remove all entries
    and add all the passed ones.
    Now we remove the one that are not in the passed one, then add the passed
    ones.
    """
    obj_ids = set()
    for obj in new_objs:
        if isinstance(obj, self.model):
            obj_ids.add(self._get_fk_val(obj, self.target_field_name))
        else:
            obj_ids.add(obj)

    db = router.db_for_write(self.through, instance=self.instance)

    to_remove = self.through._default_manager.using(db).filter(**{
                    self.source_field_name: self._fk_val
                }).exclude(**{
                    '%s__in' % self.target_field_name: obj_ids
                }).order_by(
                ).values_list(self.target_field_name, flat=True)

    self._remove_items(self.source_field_name, self.target_field_name, *to_remove)
    self.add(*new_objs)


def m2m_descriptor__set__(self, instance, value):
    if instance is None:
        raise AttributeError("Manager must be accessed via instance")

    if not self.related.field.rel.through._meta.auto_created:
        opts = self.related.field.rel.through._meta
        raise AttributeError("Cannot set values on a ManyToManyField which specifies an intermediary model. Use %s.%s's Manager instead." % (opts.app_label, opts.object_name))

    manager = self.__get__(instance)
    # replace clear + add by replace
    m2m_replace(manager, *value)

ManyRelatedObjectsDescriptor.__set__ = m2m_descriptor__set__


def reverse_m2m_descriptor__set__(self, instance, value):
    if instance is None:
        raise AttributeError("Manager must be accessed via instance")

    if not self.field.rel.through._meta.auto_created:
        opts = self.field.rel.through._meta
        raise AttributeError("Cannot set values on a ManyToManyField which specifies an intermediary model.  Use %s.%s's Manager instead." % (opts.app_label, opts.object_name))

    manager = self.__get__(instance)
    # replace clear + add by replace
    m2m_replace(manager, *value)

ReverseManyRelatedObjectsDescriptor.__set__ = reverse_m2m_descriptor__set__
