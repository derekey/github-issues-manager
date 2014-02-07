from collections import OrderedDict, defaultdict

from limpyd import model as lmodel, fields as lfields
from limpyd.utils import unique_key

from limpyd_extensions.dynamic.model import ModelWithDynamicFieldMixin
from limpyd_extensions.dynamic.fields import DynamicSortedSetField

from core import get_main_limpyd_database
from core.models import Repository, Issue

from .managers import ActivityManager


class BaseActivity(ModelWithDynamicFieldMixin, lmodel.RedisModel):
    """
    The base abstract model to store actvity, with all main methods.
    Must be subclassed for model specificities (Issue, Repository)
    """
    database = get_main_limpyd_database()
    abstract = True

    model = None
    object_id = lfields.InstanceHashField(indexable=True)

    all_activity = lfields.SortedSetField()

    change_events = lfields.SortedSetField()
    issue_comments = lfields.SortedSetField()
    issue_events = lfields.SortedSetField()
    pr_comments = lfields.SortedSetField()
    pr_commits = lfields.SortedSetField()

    @staticmethod
    def load_object(data):
        """
        Return the object for the given data, which may be an identifier, or a
        tuple (identifier, score). If the score is given, it's attached to the
        object as "activity_score"
        """
        if isinstance(data, (list, tuple)):
            identifier, score = data
        else:
            identifier, score = data, None
        code, pk = identifier.split(':')
        obj = ActivityManager.MAPPING[code].load_object(pk)
        if score is not None:
            obj.activity_score = score
        obj.activity_identifier = identifier
        return obj

    @staticmethod
    def load_objects(data):
        """
        Return objects for the given data, in the same order, using as
        fiew sql queries as possible.
        Data may be a list of identifiers, or a list of tuples :
        (identifier, score)
        """
        if not data:
            return []

        has_score = isinstance(data[0], (list, tuple))
        if has_score:
            scores_by_code = dict(data)
        else:
            scores_by_code = None

        # group by code
        by_code = defaultdict(list)
        loaded = OrderedDict()

        for one_data in data:
            if has_score:
                identifier, score = one_data
            else:
                identifier, score = one_data, None
            loaded[identifier] = None
            code, pk = identifier.split(':')
            by_code[code].append(pk)

        for code, pks in by_code.iteritems():
            for obj in ActivityManager.MAPPING[code].load_objects(pks):
                obj.activity_identifier = '%s:%s' % (code, obj.pk)
                loaded[obj.activity_identifier] = obj

        if has_score:
            for code, obj in loaded.iteritems():
                if obj:
                    obj.activity_score = '%.1f' % scores_by_code[code]

        return [obj for obj in loaded.values() if obj]

    @property
    def object(self):
        """
        Return the main object to which this activity instance is attached.
        It can be an Issue or a Repository, depending of the "model" attribute.
        """
        if not hasattr(self, '_object'):
            self._object = self.model.objects.get(pk=self.object_id.hget())
        return self._object

    def get_activity(self, codes=None, max=None, min=None, num=50, withscores=False, force_update=False, ttl=20):
        """
        Return activity for the given codes, in the reverse order (most recent
        first) with `num` elements starting from `max` score (or the highest
        available if not set), down to `min` if set. Also return a boolean
        indicating if we had as much elements as asked.
        Note that `min` may not be reached if there is more than `num` entries
        between `min` and `max`
        The returned activity is a list of identifiers as stored in the sorted
        set, but if withscores is set to True, it will return a list of tuples
        (identifier, score).
        `codes` is a list of codes to use, but can be None to use the whole
        activity (in which case the result is faster as the full list is already
        stored)
        If `force_update` is False, it will use a previously computed value,
        stored for `ttl` seconds, else it will compute it (but the cache will
        still be set for two minutes).
        """
        # by default, all codes
        if codes is None:
            codes = ActivityManager.all_codes
        else:
            codes = sorted(set(codes))

        is_full_list = codes == ActivityManager.all_codes

        min = str(min) if min else '-inf'
        max = str(max) if max else '+inf'

        if is_full_list:
            # full list, we already have the full list stored
            store_key = self.all_activity.key
        else:
            # not the full list, we will create a temp zset we wanted lists
            store_key = self.make_key(
                self._name,
                'merge',
                'codes',
                ','.join(codes),
                num,
                min,
                max,
            )

            if force_update or not self.connection.exists(store_key):

                # get the keys to union
                keys = [self.get_field(ActivityManager.MAPPING[code].limpyd_field).key for code in codes]

                # no way to directly return the result, there is no simple "zunion"
                with self.pipeline(transaction=False) as pipeline:
                    self.connection.zunionstore(store_key, keys, aggregate='MAX')
                    self.connection.connection.expire(store_key, ttl)
                    pipeline.execute()

        result = self.connection.zrevrangebyscore(
            store_key,
            min=min,
            max=max,
            start=0,
            num=num,
            withscores=withscores
        )

        return result, len(result) == num


class RepositoryActivity(BaseActivity):
    """
    Model to store the whole activity of a repository
    """
    model = Repository
    last_history = DynamicSortedSetField()

    def lock(self):
        """
        Put a lock (its a "context manager") on this repository, to avoid
        concurrent updates
        """
        return lfields.FieldLock(self.object_id, timeout=30)

    def remove_identifiers(self, identifiers, code=None):
        """
        Remove the given list of identifiers from a repository field depending
        of the code: if code is defined, use the matchinf field, sele use the
        "all_activity" field.
        Identifiers must be in the format as stored in the sorted set, aka
        "code:pk"
        """
        if not identifiers:
            return
        if code is None:
            field = self.all_activity
        else:
            field = self.get_field(ActivityManager.MAPPING[code].limpyd_field)
        field.zrem(*identifiers)

    def add_data(self, data, code=None):
        """
        Add the given data (a dict ready to use for zadd: identifiers as key,
        score as values) to a repository field depending of the code: if code is
        defined, use the matching field, else use the 'all_activity' field.
        """
        if code is None:
            field = self.all_activity
        else:
            field = self.get_field(ActivityManager.MAPPING[code].limpyd_field)
        field.zadd(**data)

    @classmethod
    def get_for_repositories(cls, pks, max=None, min=None, num=50, withscores=False, force_update=False, ttl=120):
        """
        Return the activity for the repositories represented by their pks, in
        the reverse order (most recent first) with `num` elements starting from
        `max` score (or the highest available if not set), down to `min` if set.
        Note that `min` may not be reached if there is more than `num` entries
        between `min` and `max`. Also return a boolean indicating if we had as
        much elements as asked.
        The returned activity is a list of identifiers as stored in the sorted
        sets, but if withscores is set to True, it will return a list of tuples
        (identifier, score).
        The computation (zunion of all zsets) may be long so the result is
        cached for 120 seconds (`ttl` argument), unless `force_update` is set to
        True, which will force the computation (but the cache will still be set
        for two minutes)
        Note: instead of doing a union of the "all_activity" fields for all the
        repository, we start by getting their latest values (assured to fit in
        the final min/max range) into a final sorted set, used to do the real
        revrange
        TODO: may be rewritten in LUA ?
        """

        if not pks:
            return []
        pks = sorted(set(pks))

        if len(pks) == 1:
            return Repository.objects.get(pk=pks[0]).activity.get_activity(
                codes=None,
                max=max,
                min=min,
                num=num,
                withscores=withscores,
                force_update=force_update,
                ttl=ttl
            )

        min = str(min) if min else '-inf'
        max = str(max) if max else '+inf'

        store_key = cls.make_key(
            cls._name,
            'merge',
            'repositories',
            ','.join(map(str, pks)),
            num,
            min,
            max,
        )

        if force_update or not cls.database.connection.exists(store_key):

            keys = []

            for pk in pks:
                activity, created = cls.get_or_connect(object_id=pk)
                if created:
                    continue
                last_field = activity.last_history('%s|%s|%s' % (min, max, num))
                keys.append(last_field.key)
                if not last_field.exists():
                    data = dict(activity.all_activity.zrevrangebyscore(
                        min=min,
                        max=max,
                        start=0,
                        num=num,
                        withscores=True,
                    ))
                    if not data:
                        keys.remove(last_field.key)
                        continue
                    with cls.database.pipeline(transaction=False) as pipeline:
                        last_field.delete()
                        last_field.zadd(**data)
                        cls.database.connection.expire(last_field.key, ttl)
                        pipeline.execute()

            with cls.database.pipeline(transaction=False) as pipeline:
                cls.database.connection.zunionstore(store_key, keys, aggregate='MAX')
                cls.database.connection.expire(store_key, ttl)
                pipeline.execute()

        result = cls.database.connection.zrevrangebyscore(
            store_key,
            min=min,
            max=max,
            start=0,
            num=num,
            withscores=withscores,
        )

        return result, len(result) == num


class IssueActivity(BaseActivity):
    """
    Model to store the whole activity of an issue
    """
    model = Issue

    @property
    def repository_activity(self):
        """
        Return (and create if needed) the RepositoryActivity for the repository
        of the issue associated to this current IssueActivity.
        """
        if not hasattr(self, '_repository_activity'):
            self._repository_activity, _ = RepositoryActivity.get_or_connect(
                                            object_id=self.object.repository_id)
        return self._repository_activity

    def add_entry(self, obj):
        """
        Add a specific entry to the matching list of the issue and repository
        (+"all_activity" ones)
        Its position in the sorted set will be updated if it's already in it,
        according to its new date)
        """
        manager = ActivityManager.get_for_model_instance(obj)
        # prepare the data to be inserted
        dat = manager.get_object_date(obj)
        data = manager.prepare_data([(obj.pk, dat), ])
        # insert in issue lists
        field = self.get_field(manager.limpyd_field)
        field.zadd(**data)
        self.all_activity.zadd(**data)
        # insert in the repository lists
        self.repository_activity.add_data(data, manager.code)
        self.repository_activity.add_data(data)

    def remove_entry(self, obj):
        """
        Remove the given entry for the machting list of the issue and repository
        (+"all_activity" ones)
        """
        manager = ActivityManager.get_for_model_instance(obj)
        identifier = '%s:%s' % (manager.code, obj.pk)
        # remove from the issue lists
        field = self.get_field(manager.limpyd_field)
        field.zrem(identifier)
        self.all_activity.zrem(identifier)
        # remove from the repository lists
        self.repository_activity.remove_identifiers([identifier], manager.code)
        self.repository_activity.remove_identifiers([identifier])

    def update(self):
        """
        Update all the activity for the current issue, removing items not needed
        anymore. Repository activity is updated too.
        """
        # TODO: optimize to remove only necessary items
        issue = self.object
        repository_activity = self.repository_activity

        with repository_activity.lock():

            # get stored data
            old_identifiers = self.all_activity.zmembers()

            # get fresh data
            data = {}
            for manager in ActivityManager.MAPPING.values():
                if manager.pr_only and not issue.is_pull_request:
                    continue
                data[manager.code] = manager.prepare_data(manager.get_data(issue))

            # ready to replace our data
            with self.database.pipeline(transaction=False) as pipeline:

                # remove old from repository "all_activity"
                if old_identifiers:
                    repository_activity.remove_identifiers(old_identifiers)

                # reset all fields with new data
                self.all_activity.delete()
                for code, manager in ActivityManager.MAPPING.iteritems():
                    data_for_code = data.get(code)

                    # manage issue

                    field = self.get_field(manager.limpyd_field)

                    # full clean of the field
                    field.delete()

                    if data_for_code:
                        # specific activity field
                        field.zadd(**data_for_code)
                        # "all_activity" field
                        self.all_activity.zadd(**data_for_code)

                    # manage repository

                    # remove old ones from repository activity
                    if old_identifiers:
                        repository_activity.remove_identifiers([i for i in old_identifiers if i.startswith(code)], code)

                    if data_for_code:
                        # add new ones in the specific activity field for repository
                        repository_activity.add_data(data_for_code, code)
                        # add new ones in the repository "all_activity"
                        repository_activity.add_data(data_for_code)

                pipeline.execute()
