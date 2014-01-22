from collections import OrderedDict, defaultdict

from limpyd import model as lmodel, fields as lfields
from limpyd.utils import unique_key

from core import main_limpyd_database
from core.models import Repository, Issue

from .managers import ActivityManager


class BaseActivity(lmodel.RedisModel):
    """
    The base abstract model to store actvity, with all main methods.
    Must be subclassed for model specificities (Issue, Repository)
    """
    database = main_limpyd_database
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
    def load_object(identifier):
        """
        Return the object for the given identifier
        """
        code, pk = identifier.split(':')
        return ActivityManager.MAPPING[code].load_object(pk)

    @staticmethod
    def load_objects(identifiers):
        """
        Return objects for the given identifiers, in the same order, using as
        fiew sql queries as possible
        """
        # group by code
        by_code = defaultdict(list)
        loaded = OrderedDict()
        for identifier in identifiers:
            loaded[identifier] = None
            code, pk = identifier.split(':')
            by_code[code].append(pk)
        for code, pks in by_code.iteritems():
            for obj in ActivityManager.MAPPING[code].load_objects(pks):
                loaded['%s:%s' % (code, obj.pk)] = obj
        return (obj for obj in loaded.values() if obj)

    @property
    def object(self):
        """
        Return the main object to which this activity instance is attached.
        It can be an Issue or a Repository, depending of the "model" attribute.
        """
        if not hasattr(self, '_object'):
            self._object = self.model.objects.get(pk=self.object_id.hget())
        return self._object

    def get_activity(self, codes=None, start=0, stop=-1, withscores=False, force_update=False):
        """
        Return activity for the given codes, starting at the "start" item,
        ending at the "end" one.
        The returned activity is a list of identifiers as stored in the sorted
        set, but if withscores is set to True, it will return a list of tuples
        (score, identifier).
        "codes" is a list of codes to use, but can be None to use the whole
        activity.
        If force_updates is False, it will use an possibly stored value, else it
        will compute it (it can be heavy). Actually, only the whole activity is
        precomputed.
        """
        # by default, all codes
        if codes is None:
            codes = ActivityManager.all_codes
        else:
            codes = sorted(codes)

        is_full_list = codes == ActivityManager.all_codes

        if is_full_list and not force_update:
            return self.all_activity.zrevrange(start, stop, withscores)

        # get the keys to union
        keys = [self.get_field(ActivityManager.MAPPING[code].limpyd_field).key for code in codes]

        if is_full_list:
            store_key = self.all_activity.key
        else:
            store_key = unique_key(self.connection)

        # no way to directly return the result, there is no simple "zunion"
        self.connection.zunionstore(store_key, keys)

        result = self.connection.zrevrange(store_key, start, stop, withscores)

        if not is_full_list:
            self.connection.delete(store_key)

        return result


class RepositoryActivity(BaseActivity):
    """
    Model to store the whole activity of a repository
    """
    model = Repository

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
    def get_for_repositories(cls, pks, start=0, stop=-1, withscores=False, force_update=False):
        """
        Return the activity for the repositories represented by their pks
        starting at the "start" item, ending at the "end" one.
        The returned activity is a list of identifiers as stored in the sorted
        set, but if withscores is set to True, it will return a list of tuples
        (score, identifier).
        The computation (zunion of all zsets) may be long so the result is
        cached for two minutes, unless force_update is set to True, which will
        force the computation (but the cache will still be set for two minutes)
        """
        if not pks:
            return []

        store_key = cls.make_key(
                cls._name,
                'merge',
                'repositories',
                ','.join(map(str, sorted(pks)))
            )

        if force_update or not main_limpyd_database.connection.exists(store_key):

            keys = [
                cls.get_or_connect(object_id=pk)[0].all_activity.key
                for pk in pks
            ]

            main_limpyd_database.connection.zunionstore(store_key, keys)
            main_limpyd_database.connection.expire(store_key, 120)  # keep for 2 minutes

        return main_limpyd_database.connection.zrevrange(store_key, start, stop, withscores)


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
        dat = getattr(obj, manager.date_field)
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
            with main_limpyd_database.pipeline(transaction=False) as pipeline:

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
