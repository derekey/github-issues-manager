
from datetime import datetime, timedelta
import time
from dateutil.parser import parse

from django.conf import settings

from limpyd import fields
from limpyd.contrib.database import PipelineDatabase
from limpyd_jobs.models import BaseJobsModel, Job as LimpydJob, Queue as LimpydQueue
from limpyd_jobs.workers import Worker as LimpydWorker, logger

from core.ghpool import Connection
from core.models import GithubUser


logger.addHandler(settings.WORKERS_LOGGER_CONFIG['handler'])

main_database = PipelineDatabase(**settings.WORKERS_REDIS_CONFIG)
BaseJobsModel.use_database(main_database)


class Worker(LimpydWorker):
    """
    Base worker to use by specifyng the job model to use
    """
    logger_level = settings.WORKERS_LOGGER_CONFIG['level']

    def __init__(self, *args, **kwargs):
        """
        By default use the queue name defined in the job model
        """
        job_model = kwargs.get('job_model', self.job_model)
        if hasattr(job_model, 'queue_name'):
            self.name = job_model.queue_name
        super(Worker, self).__init__(*args, **kwargs)

    def execute(self, job, queue):
        """
        Simply call the `run` method of the job
        """
        return job.run(queue)

    def job_success(self, job, queue, job_result):
        """
        When the default job_success is finished, call the `on_success` method
        of the job
        """
        super(Worker, self).job_success(job, queue, job_result)
        job.on_success(queue, job_result)

    def job_success_message(self, job, queue, job_result):
        """
        Add the string returned by the `success_message_addon` method of the job
        to the default success message
        """
        message = super(Worker, self).job_success_message(job, queue, job_result)
        return message + job.success_message_addon(queue, job_result)


class Job(LimpydJob):
    """
    An abstract job model that provides empty methods needed by the base Worker.
    In addition, the add_job class method does not need any queue-name as it's
    defined as a class attribute
    """
    abstract = True
    queue_name = None
    gh_args = fields.HashField()  # will store info to create a Github connection

    def run(self, queue):
        return None

    def on_success(self, queue, result):
        return None

    def success_message_addon(self, queue, result):
        return ''

    @classmethod
    def add_job(cls, identifier, priority=0, queue_model=None, prepend=False, **fields_if_new):
        if 'gh' in fields_if_new:
            fields_if_new['gh_args'] = fields_if_new['gh']._connection_args
            del fields_if_new['gh']
        return super(Job, cls).add_job(identifier, cls.queue_name, priority, queue_model, prepend, **fields_if_new)

    @property
    def gh(self):
        """
        Return a Connection object based on arguments saved in the job
        """
        return Connection.get(**self.gh_args.hgetall())

    @property
    def gh_user(self):
        """
        Return the user used to make the connection
        """
        return GithubUser.objects.get(username=self.gh_args.hget('username'))


class DjangoModelJob(Job):
    """
    An abstract job model that provides stuff to get objects from the django
    orm based on the job's identifier
    """
    abstract = True
    model = None

    def get_django_object(self, **filters):
        """
        Call the `get` method of the model's manager with the given filters and
        return an django model instance
        """
        return self.model.objects.get(**filters)

    def get_django_object_from_identifier(self):
        """
        Return a django model instance using the job's identifier
        """
        return self.get_django_object(id=self.identifier.hget())
    object = property(get_django_object_from_identifier)


class DelayedQueue(LimpydQueue):
    delayed = fields.SortedSetField()
    next_time_ready = fields.InstanceHashField()

    @classmethod
    def datetime_to_score(cls, dt):
        return time.mktime(dt.timetuple()) + dt.microsecond / 1000000.0

    def delay_job(self, job):
        """
        Add the delayed job to the delayed zset
        """
        delayed_until = job.delayed_until.hget()
        if not delayed_until:
            delayed_until = datetime.utcnow()
        else:
            delayed_until = parse(delayed_until)
        delayed_until = self.datetime_to_score(delayed_until)
        self.delayed.zadd(delayed_until, job.pk.get())

        self.update_next_time_ready()

    def get_first_entry(self):
        """
        Return the first entry in the delayed zset
        """
        entries = self.delayed.zrange(0, 0, withscores=True)
        return entries[0] if entries else None

    def update_next_time_ready(self):
        """
        Update the next_time_ready field with the time of the first job
        that will be ready (ie the first entry in the zset)
        """
        # get the first job which will be ready
        first_entry = self.get_first_entry()

        # save the next time we need to get the job
        if not first_entry:
            self.next_time_ready.delete()
            return None
        else:
            delayed_until = first_entry[1]
            self.next_time_ready.hset(delayed_until)
            return delayed_until

    def get_first_ready(self, now_timestamp=None):
        """
        Return the first job of the zset if it is ready to be ran
        """
        # stop here if weknow we have nothing
        next_time_ready = self.next_time_ready.hget()
        if not next_time_ready:
            # in case of next_time_ready was emptyied but jobs are stille
            # delayed, fill the value again
            if self.delayed.zcard():
                self.update_next_time_ready()
            return None

        # get when we are if nobdy told us :)
        if not now_timestamp:
            now_timestamp = self.datetime_to_score(datetime.utcnow())

        # the first job will be ready later, abort
        if float(next_time_ready) > now_timestamp:
            return None

        # to protect other process to get the same job
        self.next_time_ready.delete()

        # get the first entry (the job to be run)
        first_entry = self.get_first_entry()

        # no first entry, another worker took it from us !
        if not first_entry:
            return None

        # split into vars for lisibility
        job_pk, delayed_until = first_entry

        # the date of the job is in the future, another work took the job we
        # wanted, so we let this job here and update the next_time_ready
        if delayed_until > now_timestamp:
            self.update_next_time_ready()
            return None

        # remove the entry we just got to be able to run the job
        self.delayed.zrem(job_pk)

        # and ready for the next
        self.update_next_time_ready()

        # and return the pk of the job to run
        return job_pk

    @classmethod
    def get_delayed_job(cls, name):
        # precompute the date
        now_timestamp = cls.datetime_to_score(datetime.utcnow())

        # get all the queues for the given name
        queues = cls.collection(name=name).sort(by='-priority').instances()

        # find the first queue with a job ready
        for queue in queues:
            job_pk = queue.get_first_ready(now_timestamp=now_timestamp)
            if job_pk:
                return queue, job_pk

        # no job found...
        return None


class DelayableJob(Job):
    abstract = True
    delayed_until = fields.InstanceHashField()
    queue_model = DelayedQueue

    @classmethod
    def add_job(cls, identifier, priority=0, queue_model=None, prepend=False, **fields_if_new):
        """
        The "delayable_until" field, passed in `fields_if_new` can be a timedelta
        (will be added to utcnow), or a datetime
        """
        if fields_if_new.get('delayed_until'):
            if fields_if_new.get('delayed_for'):
                raise ValueError('delayed_until and delayed_for arguments are exclusives')
            if isinstance(fields_if_new['delayed_until'], datetime):
                fields_if_new['delayed_until'] = str(fields_if_new['delayed_until'])
            else:
                raise ValueError('Invalid delayed_until argument: must be a datetime object')
        else:
            fields_if_new.pop('delayed_until', None)

        if fields_if_new.get('delayed_for'):
            if isinstance(fields_if_new['delayed_for'], timedelta):
                fields_if_new['delayed_until'] = str(datetime.utcnow() + fields_if_new['delayed_for'])
            else:
                raise ValueError('Invalid delayed_for argument: must be a timedelta object')
            fields_if_new.pop('delayed_for', None)

        return super(DelayableJob, cls).add_job(identifier, priority, queue_model, prepend, **fields_if_new)


class DelayedWorker(Worker):
    queue_model = DelayedQueue

    def wait_for_job(self):
        """
        Before getting a job from the normal feed, check if we have delayable
        ones that are ready.
        Then get one from the feed and delay it if needed
        """
        # try to get a delayed job that is ready
        queue_and_job = self.queue_model.get_delayed_job(self.name)
        if queue_and_job:
            # found return the queue and the job
            return queue_and_job[0], self.get_job(queue_and_job[1])

        # no delayed job ready, get one from the normal feed
        queue_and_job = super(DelayedWorker, self).wait_for_job()
        if queue_and_job is None:
            return None

        # check if the queue is a delayed one (if not, process the job)
        queue, job = queue_and_job
        if not isinstance(queue, DelayedQueue):
            return queue_and_job

        # check if the job is a delayed one (if not, process it)
        if not hasattr(job, 'delayed_until'):
            return queue_and_job

        # check if the job has delayed informations (if not, process it)
        delayed_until = job.delayed_until.hget()
        if not delayed_until:
            return queue_and_job

        # check that the job is ready to be processed (if yes, do it)
        if delayed_until <= str(datetime.utcnow()):
            return queue_and_job

        # ok we are not ready to process the job, delay it
        queue.delay_job(job)
        self.log('[%s|%s] job delayed until %s' % (
                                queue.name.hget(),
                                job.identifier.hget(),
                                delayed_until
                            ))

        # and so we have nothing to do for now
        return None
