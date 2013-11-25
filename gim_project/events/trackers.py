# inspired by http://justcramer.com/2010/12/06/tracking-changes-to-fields-in-django/

from django.db.models.signals import post_init, post_save

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
        if kwargs['created']:
            event = cls.add_created_event(instance)
        else:
            changed_fields = instance.changed_fields()
            if changed_fields:
                event = cls.add_changed_event(instance, changed_fields)
                cls.add_changed_parts(instance, changed_fields, event)

        return event

    @classmethod
    def add_changed_parts(cls, instance, changed_fields, event):
        from .models import EventPart

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
                EventPart.objects.bulk_create([
                    EventPart(event=event, **part)
                        for part in parts
                ])

    @classmethod
    def _prepare_m2m_fields(cls):
        for field in cls.fields:
            if not field.endswith('__ids'):
                continue
            m2m_field = field[:-5]
            _, _, _, is_m2m = cls.model._meta.get_field_by_name(m2m_field)
            if not is_m2m:
                continue

            @property
            def get_m2m_ids(self):
                return list(getattr(self, m2m_field).values_list('id', flat=True))
            setattr(cls.model, field, get_m2m_ids)

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
              'state', 'merged', 'mergeable', )
    model = Issue

    @classmethod
    def add_created_event(cls, instance):
        from .models import Event

        return Event.objects.create(
            repository=instance.repository,
            issue=instance,
            created_at=instance.updated_at,
            related_object=instance,
            title="Issue #%s was created" % instance.number,
        )

    @classmethod
    def add_changed_event(cls, instance, changed_fields):
        from .models import Event

        return Event.objects.create(
            repository=instance.repository,
            issue=instance,
            created_at=instance.updated_at,
            related_object=instance,
            title="Issue #%s was changed" % instance.number,
        )

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
            'field': 'merged',
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
    def event_part_for_labels__ids(instance, new, old):
        diff = {
            'added': set(new).difference(old),
            'removed': set(old).difference(new),
        }

        # seems that nothing changed...
        if not diff['added'] and not diff['removed']:
            return []

        import debug
        # get all added/removed labels from DB in one uery with label type
        labels_by_id = Label.objects.select_related('label_type').in_bulk(
                                        diff['added'].union(diff['removed']))

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

            result.append({
                'field': 'label_type',
                'new_value': {
                    'label_type': {
                        'id': type.id,
                        'name': type.name,
                    },
                    'labels': modes.get('added', []),
                },
                'old_value': {
                    'labels': modes.get('removed', []),
                },
            })

        # then add the untyped labels
        if None in by_type:
            if 'added' in by_type[None]:
                result.append({
                    'field': 'labels',
                    'old_value': {'labels': []},
                    'new_value': {
                        'labels': by_type[None]['added']
                    }
                })
            if 'removed' in by_type[None]:
                result.append({
                    'field': 'labels',
                    'new_value': {'labels': []},
                    'old_value': {
                        'labels': by_type[None]['removed']
                    }
                })

        return result


IssueTracker.connect()
