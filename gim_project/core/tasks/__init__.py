import json

from django.conf import settings

from limpyd import fields
from limpyd.contrib.database import PipelineDatabase
from limpyd_jobs.models import (
                                BaseJobsModel,
                                Job as LimpydJob,
                                Queue as LimpydQueue,
                                Error as LimpydError,
                            )
from limpyd_jobs.workers import Worker as LimpydWorker, logger

from core.ghpool import Connection, ApiError
from core.models import GithubUser


logger.addHandler(settings.WORKERS_LOGGER_CONFIG['handler'])

main_database = PipelineDatabase(**settings.WORKERS_REDIS_CONFIG)
BaseJobsModel.use_database(main_database)

NAMESPACE = 'gim'


class Queue(LimpydQueue):
    namespace = NAMESPACE


class Error(LimpydError):
    namespace = NAMESPACE

    # store the result of the githubapi request and response in case of error
    # they are set by json.dumps
    gh_request = fields.InstanceHashField()
    gh_response = fields.InstanceHashField()


class Worker(LimpydWorker):
    """
    Base worker:
    - overrides job_success_message to call job.success_message_addon
    """
    queue_model = Queue
    error_model = Error
    logger_name = 'gim.jobs'
    logger_level = settings.WORKERS_LOGGER_CONFIG['level']
    requeue_times = 1000

    def job_success_message(self, job, queue, job_result):
        """
        Add the string returned by the `success_message_addon` method of the job
        to the default success message
        """
        message = super(Worker, self).job_success_message(job, queue, job_result)
        return message + job.success_message_addon(queue, job_result)

    def additional_error_fields(self, job, queue, exception, trace=None):
        """
        Save the response of an ApiError
        """
        fields = super(Worker, self).additional_error_fields(job, queue, exception, trace)

        if isinstance(exception, ApiError):
            fields['gh_request'] = json.dumps(exception.request)
            fields['gh_response'] = json.dumps(exception.response)

        return fields


class Job(LimpydJob):
    """
    An abstract job model that provides empty methods needed our the base Worker.
    In addition, the add_job class method does not need any queue-name as it's
    defined as a class attribute
    """
    abstract = True
    namespace = NAMESPACE
    queue_model = Queue
    queue_name = None
    gh_args = fields.HashField()  # will store info to create a Github connection

    def run(self, queue):
        return None

    @property
    def queue(self):
        """
        Helper to easily get the job's queue
        """
        priority = self.priority.hget()
        return self.queue_model.get_queue(name=self.queue_name, priority=priority)

    def success_message_addon(self, queue, result):
        """
        The string returned by this method will be added to the message logged
        when the job is successfully executed
        """
        return ''

    @classmethod
    def add_job(cls, *args, **kwargs):
        """
        Replace the `gh` argument by a `gh_args` one by getting the connection
        arguments from it.
        """

        if 'gh' in kwargs:
            kwargs['gh_args'] = kwargs['gh']._connection_args
            del kwargs['gh']

        return super(Job, cls).add_job(*args, **kwargs)

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
