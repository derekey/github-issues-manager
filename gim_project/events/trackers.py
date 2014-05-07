# inspired by http://justcramer.com/2010/12/06/tracking-changes-to-fields-in-django/

from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_init, post_save, m2m_changed

from core.models import GithubUser,  Milestone, Issue, Label

UNSAVED = dict()


class ChangeTracker(object):

    fields = ()
    model = None

    @classmethod
    def _instance_update_fields(cls, instance):
        if instance.id:
            instance._dirty_fields = dict((f, getattr(instance, f)) for f in cls.fields)
        else:
            instance.__data = UNSAVED

    @classmethod
    def _instance_post_init(cls, instance, **kwargs):
        cls._instance_update_fields(instance)

    @classmethod
    def _instance_post_save(cls, instance, **kwargs):
        cls.create_event(instance, **kwargs)
        cls._instance_update_fields(instance)

    @classmethod
    def create_event(cls, instance, **kwargs):
        event = None
        if kwargs.get('created'):
            event = cls.add_created_event(instance)
        else:
            changed_fields = instance.changed_fields()
            if changed_fields:
                event = cls.add_changed_event(instance, changed_fields)
                if not cls.add_changed_parts(instance, changed_fields, event):
                    event.delete()

        return event

    @classmethod
    def add_changed_parts(cls, instance, changed_fields, event):

        parts_count = 0

        for field in changed_fields:
            new = getattr(instance, field)
            old = changed_fields[field]

            try:
                method = getattr(cls, 'event_part_for_%s' % field)
                parts = method(instance, new, old)
            except AttributeError:
                parts = [{
                    'field': field,
                    'old_value': {field: old},
                    'new_value': {field: new},
                }]

            if parts:
                event.add_parts(parts)
                parts_count += len(parts)

        return parts_count > 0

    @classmethod
    def _prepare_m2m_fields(cls):
        for field in cls.fields:
            if not field.endswith('__ids'):
                continue
            m2m_field = field[:-5]
            _, _, _, is_m2m = cls.model._meta.get_field_by_name(m2m_field)
            if not is_m2m:
                continue

            # use a function to avoid var pbms in loops with closures
            def _prepare_m2m_field(cls, m2m_field, field):

                @property
                def get_m2m_ids(self):
                    return getattr(self, m2m_field).order_by().values_list('id', flat=True)
                setattr(cls.model, field, get_m2m_ids)

                # we need to check for m2m updates
                through = getattr(cls.model, m2m_field).through

                def _instance_m2m_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
                    # if reverse: instance is related object, pk_set are from cls.model
                    # if not: instance is from cls.model, pk_set are related objects

                    is_replace_mode = getattr(instance, '_signal_replace_mode', {}).get(model, False)
                    if is_replace_mode and action not in ('pre_replace', 'post_replace'):
                        # in replace mode, ignore the add, remove, clear...
                        return

                    # prepare...
                    self_name = cls.model._meta.module_name
                    if action in ('pre_clear', 'post_clear', 'pre_replace', 'post_replace'):
                        if not hasattr(instance, '_m2m_dirty_fields'):
                            instance._m2m_dirty_fields = {}

                    # in pre_clear/pre_replace mode, we node to get the current
                    # existing values to know which values to remove in post_*
                    if action in ('pre_clear', 'pre_replace'):

                        # reverse mode, the existing are from "cls.model" linked to the instance
                        if reverse:
                            existing = set(cls.model.objects.filter(**{m2m_field: instance})
                                                          .order_by()
                                                          .values_list('pk', flat=True))
                            instance._m2m_dirty_fields[self_name] = existing

                        # direct mode, the existing are related objects accessible via field
                        else:
                            existing = set(getattr(instance, field))  # get_m2m_ids directly gives us pks
                            instance._m2m_dirty_fields[field] = existing

                        return

                    operations = []

                    # in post_add/remove mode, we know which one to add/remove
                    if action in ('post_add', 'post_remove'):
                        if not pk_set:
                            return

                        to_add, to_remove = set(), set()
                        the_set = to_add if action == 'post_add' else to_remove

                        # in reverse mode, the instance is the obj to add/remove,
                        # and the updated objects are cls.model from pk_set
                        if reverse:
                            objs = cls.model.objects.filter(pk__in=pk_set)
                            the_set.add(instance.id)

                        # in direct mode, the instance is the cls.model to update,
                        # and the objects to add/remove are taken from pk_set
                        else:
                            objs = [instance]
                            the_set.update(pk_set)

                        if the_set:
                            operations.append((objs, to_add, to_remove))

                    # in post_clear mode, we need to retrieve pk_set saved in pre_clear
                    # then we work like for pre_remove
                    elif action == 'post_clear':
                        to_remove = set()
                        if reverse:
                            existing = instance._m2m_dirty_fields.pop(self_name, set())
                            objs = cls.model.objects.filter(pk__in=existing)
                            to_remove.add(instance.id)
                        else:
                            existing = instance._m2m_dirty_fields.pop(field, set())
                            objs = [instance]
                            to_remove.update(existing)

                        if to_remove:
                            operations.append((objs, set(), to_remove))

                    elif action == 'post_replace':
                        if reverse:
                            existing = instance._m2m_dirty_fields.pop(self_name, set())
                            removed_from_objs = existing - pk_set
                            added_to_objs = pk_set - existing

                            if removed_from_objs:
                                operations.append((removed_from_objs, set(), set([instance.id])))
                            if added_to_objs:
                                operations.append((added_to_objs, set([instance.id]), set()))

                        else:
                            existing = instance._m2m_dirty_fields.pop(field, set())
                            objs = [instance]
                            to_remove = existing - pk_set
                            to_add = pk_set - existing

                            if to_remove or to_add:
                                operations.append((objs, to_add, to_remove))

                    else:
                        # ignore other modes than [pre|post]_clear and post_[add|remove]
                        return

                    # so, trigger update event for all objects
                    for objs, to_add, to_remove in operations:
                        for obj in objs:
                            # initiate saving dirty_fields, but we now have the definitive
                            # values here
                            cls._instance_post_init(obj)
                            # so we update the dirty_field entry by adding the ones to remove, and remove the ones to add
                            # so the tracker, by comparing from DB, will see the difference
                            current = set(obj._dirty_fields.get(field, []))
                            obj._dirty_fields[field] = list(current.union(to_remove) - to_add)
                            # now trigger the post_save to view the difference and create events
                            cls._instance_post_save(obj)

                m2m_changed.connect(_instance_m2m_changed, sender=through, weak=False)

            _prepare_m2m_field(cls, m2m_field, field)

    @classmethod
    def connect(cls):
        cls._prepare_m2m_fields()

        def _instance_post_init(sender, instance, **kwargs):
            cls._instance_post_init(instance, **kwargs)
        post_init.connect(_instance_post_init, sender=cls.model, weak=False)

        def _instance_post_save(sender, instance, **kwargs):
            cls._instance_post_save(instance, **kwargs)
        post_save.connect(_instance_post_save, sender=cls.model, weak=False)

        def field_has_changed(self, field):
            "Returns `True` if `field` has changed since initialization."
            if getattr(self, '_dirty_fields', UNSAVED) is UNSAVED:
                return False
            return self._dirty_fields.get(field) != getattr(self, field)
        cls.model.field_has_changed = field_has_changed

        def field_old_value(self, field):
            "Returns the previous value of `field`"
            return getattr(self, '_dirty_fields', UNSAVED).get(field)
        cls.model.field_old_value = field_old_value

        def changed_fields(self):
            "Returns a list of changed attributes."
            if getattr(self, '_dirty_fields', UNSAVED) is UNSAVED:
                return {}
            return dict([(k, v) for k, v in self._dirty_fields.iteritems()
                                if v != getattr(self, k)])
        cls.model.changed_fields = changed_fields


class IssueTracker(ChangeTracker):
    fields = ('title', 'body', 'labels__ids', 'assignee_id', 'milestone_id',
              'state', 'merged', 'mergeable', 'mergeable_state')
    model = Issue

    @classmethod
    def add_created_event(cls, instance):
        from .models import Event

        event = Event.objects.create(
            repository=instance.repository,
            issue=instance,
            created_at=instance.created_at,
            is_update=False,
            related_object=instance,
            title="%s #%s was created" % (instance.type.capitalize(), instance.number),
        )

        # add some parts to the events for some fields
        parts = []

        if instance.milestone_id:
            parts.extend(cls.event_part_for_milestone_id(instance, instance.milestone_id, None))

        if instance.assignee_id:
            parts.extend(cls.event_part_for_assignee_id(instance, instance.assignee_id, None))

        if instance.state == 'closed':
            parts.extend(cls.event_part_for_state(instance, 'closed', 'open'))

        if instance.is_pull_request:

            if instance.mergeable is not None:
                parts.extend(cls.event_part_for_mergeable(instance, instance.mergeable, None))

            if instance.state == 'closed' and instance.merged is not None:
                parts.extend(cls.event_part_for_merged(instance, instance.merged, None))

        parts.extend(cls.event_part_for_labels__ids(instance, instance.labels__ids, []))

        if parts:
            event.add_parts(parts)

        instance.repository.counters.update_from_created_issue(instance)

        return event

    @classmethod
    def add_changed_event(cls, instance, changed_fields):
        from .models import Event

        event, created = Event.objects.get_or_create(
            repository=instance.repository,
            issue=instance,
            created_at=instance.updated_at,
            is_update=True,
            related_content_type=ContentType.objects.get_for_model(instance),
            related_object_id=instance.pk,
            title="%s #%s was changed" % (instance.type.capitalize(), instance.number),
        )

        instance.repository.counters.update_from_updated_issue(instance, changed_fields)

        return event

    @staticmethod
    def event_part_for_title(instance, new, old):
        if old:
            return [{
                'field': 'title',
                'old_value': {'title': old},
                'new_value': {'title': new},
            }]

    @staticmethod
    def event_part_for_body(instance, new, old):
        if old:
            return [{
                'field': 'body',
                'old_value': {'body': old},
                'new_value': {'body': new},
            }]

    @staticmethod
    def event_part_for_assignee_id(instance, new, old):
        ids = []
        if new:
            ids.append(new)
        if old:
            ids.append(old)
        users_by_id = GithubUser.objects.in_bulk(ids)

        result = {
            'field': 'assignee',
        }
        if new and new in users_by_id:
            result['new_value'] = {
                'id': new,
                'username': users_by_id[new].username,
                'avatar_url': users_by_id[new].avatar_url,
            }
        if old and old in users_by_id:
            result['old_value'] = {
                'id': old,
                'username': users_by_id[old].username,
                'avatar_url': users_by_id[old].avatar_url,
            }

        return [result]

    @staticmethod
    def event_part_for_milestone_id(instance, new, old):
        ids = []
        if new:
            ids.append(new)
        if old:
            ids.append(old)
        milestones_by_id = Milestone.objects.in_bulk(ids)

        result = {
            'field': 'milestone',
        }
        if new and new in milestones_by_id:
            result['new_value'] = {
                'id': new,
                'title': milestones_by_id[new].title,
            }
        if old and old in milestones_by_id:
            result['old_value'] = {
                'id': old,
                'title': milestones_by_id[old].title,
            }

        return [result]

    @staticmethod
    def event_part_for_state(instance, new, old):
        result = {
            'field': 'state',
            'old_value': {'state': old},
            'new_value': {'state': new},
        }

        if new == 'closed'and instance.closed_by_id:
            result['new_value']['by'] = {
                'username': instance.closed_by.username,
                'avatar_url': instance.closed_by.avatar_url,
            }
        # TODO : uncomment when repoened_by will be implemented
        # elif new == 'open' and instance.reopened_by_id:
        #     result['new_value']['by'] = {
        #         'username': instance.reopened_by.username,
        #         'avatar_url': instance.reopened_by.avatar_url,
        #     }

        return [result]

    @staticmethod
    def event_part_for_merged(instance, new, old):
        if old is None and not new:
            return []
        if instance.state != 'closed':
            return []

        result = {
            'field': 'merged',
            'old_value': {'merged': old},
            'new_value': {'merged': new},
        }

        if new and instance.merged_by_id:
            result['new_value']['by'] = {
                'username': instance.merged_by.username,
                'avatar_url': instance.merged_by.avatar_url,
            }

        return [result]

    @staticmethod
    def event_part_for_mergeable(instance, new, old):
        if new is None:
            return []
        if old is None and not new:
            return []
        if instance.state == 'closed':
            return []

        return [{
            'field': 'mergeable',
            'old_value': {'mergeable': old},
            'new_value': {'mergeable': new, 'mergeable_state': instance.mergeable_state},
        }]

    @staticmethod
    def event_part_for_mergeable_state(instance, new, old):
        if instance.mergeable is None:
            return []
        if old is None and not new:
            return []
        if instance.state == 'closed':
            return []

        return [{
            'field': 'mergeable_state',
            'old_value': {'mergeable_state': old},
            'new_value': {'mergeable_state': new, 'mergeable': instance.mergeable},
        }]

    @staticmethod
    def event_part_for_labels__ids(instance, new, old):
        if old is None:
            old = []

        diff = {
            'added': set(new).difference(old),
            'removed': set(old).difference(new),
            'before': set(old),
            'after': set(new),
        }

        # seems that nothing changed...
        if not diff['added'] and not diff['removed']:
            return []

        # get all added/removed labels from DB in one query with label type
        labels_by_id = Label.objects.select_related('label_type').in_bulk(
                                            diff['before'] | diff['after'])

        # regroup added/removed labels by type
        # by_type = {
        #     'label_type_obj': {
        #         'added': [
        #             {'name': 'label typed name', 'color': '#xxxxxx', 'id': xx}
        #         ],
        #         'removed': [...]
        #     },
        #     ...
        #     None: {...}
        # }
        by_type = {}
        for mode, ids in diff.items():
            for label_id in ids:
                if label_id not in labels_by_id:
                    continue
                label = labels_by_id[label_id]
                type = label.label_type if label.label_type_id else None
                by_type.setdefault(type, {}).setdefault(mode, []).append({
                    'name': label.typed_name,
                    'color': label.color,
                    'id': label.id,
                })

        result = []

        # add the typed labels first
        for type, modes in by_type.items():
            if type is None:
                continue

            if not modes.get('added') and not modes.get('removed'):
                continue

            result.append({
                'field': 'label_type',
                'new_value': {
                    'label_type': {
                        'id': type.id,
                        'name': type.name,
                    },
                    'labels': modes.get('after', []),
                    'added': modes.get('added', []),
                    'removed': modes.get('removed', []),
                },
                'old_value': {
                    'label_type': {
                        'id': type.id,
                        'name': type.name,
                    },
                    'labels': modes.get('before', []),

                },
            })

        # then add the untyped labels
        if None in by_type:
            if 'added' in by_type[None]:
                result.append({
                    'field': 'labels',
                    'new_value': {
                        'labels': by_type[None]['added']
                    }
                })
            if 'removed' in by_type[None]:
                result.append({
                    'field': 'labels',
                    'old_value': {
                        'labels': by_type[None]['removed']
                    }
                })

        return result


IssueTracker.connect()
