import json

from django.conf import settings
from django.db import DatabaseError

from limpyd import fields
from limpyd.model import MetaRedisModel

from limpyd_jobs import STATUSES
from limpyd_jobs.models import (
                                BaseJobsModel,
                                Job as LimpydJob,
                                Queue as LimpydQueue,
                                Error as LimpydError,
                            )
from limpyd_jobs.utils import compute_delayed_until
from limpyd_jobs.workers import Worker as LimpydWorker, logger

from core import get_main_limpyd_database

from core.ghpool import ApiError
from core.models import GithubUser

from . import JobRegistry

logger.addHandler(settings.WORKERS_LOGGER_CONFIG['handler'])

BaseJobsModel.use_database(get_main_limpyd_database())

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
        return message + (job.success_message_addon(queue, job_result) or '')

    def additional_error_fields(self, job, queue, exception, trace=None):
        """
        Save the response of an ApiError
        """
        fields = super(Worker, self).additional_error_fields(job, queue, exception, trace)

        if isinstance(exception, ApiError):
            fields['gh_request'] = json.dumps(exception.request)
            fields['gh_response'] = json.dumps(exception.response)

        if isinstance(exception, DatabaseError):
            self.log('DatabaseError detected, force end', level='critical')
            self.end_forced = True

        return fields


class JobMetaClass(MetaRedisModel):

    def __new__(mcs, name, base, attrs):
        it = super(JobMetaClass, mcs).__new__(mcs, name, base, attrs)
        if not it.abstract:
            JobRegistry.add(it)
        return it


class Job(LimpydJob):
    """
    An abstract job model that provides empty methods needed our the base Worker.
    In addition, the add_job class method does not need any queue-name as it's
    defined as a class attribute
    """
    __metaclass__ = JobMetaClass

    abstract = True
    namespace = NAMESPACE
    queue_model = Queue
    queue_name = None
    gh_args = fields.HashField()  # will store info to create a Github connection
    clonable_fields = ()

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

    def _get_gh(self):
        """
        Return a Connection object based on arguments saved in the job, or by
        type of permission, to get one from the Token model
        """
        from core.limpyd_models import Token

        args = self.gh_args.hgetall()
        if 'access_token' not in args:
            args = None

        permission = getattr(self, 'permission', 'read')

        token = None

        # we have connection args: get the token if available
        if args:
            try:
                token_kwargs = {'token': args['access_token']}
                # ignore the available flag for "self"
                if permission != 'self':
                    token_kwargs['available'] = 1
                try:
                    token = Token.get(**token_kwargs)
                except IndexError:
                    # changed during the "get"... retry once
                    # explanation: the get first check the length of the result
                    # and if it's 1, then it retrieves the first, but in the
                    # meantime, the data may have changed and there is result
                    # anymore...
                    token = Token.get(**token_kwargs)
                except:
                    raise
            except (Token.DoesNotExist, KeyError):
                pass
            else:
                # final check on remaining api calls
                if int(token.rate_limit_remaining.get() or 0):
                    return token.gh

        # no token, try to get one...
        repository = None

        if permission == 'self':
            # forced to use the current one, but not available...
            pass
        else:

            # if we have a repository, get one following permission
            repository = getattr(self, 'repository')
            if repository:
                if repository.private and permission not in ('admin', 'push', 'pull'):
                    # force correct permission if repository is private
                    permission = 'pull'
                token = Token.get_one_for_repository(repository.pk, permission)

            # no repository, not "self", but want one ? don't know why but ok...
            else:
                token = Token.get_one()

        # if we don't have token it's that there is no one available: we delay
        # the job
        if not token:
            self.status.hset(STATUSES.DELAYED)

            if hasattr(self, 'delay_for_gh'):
                # use the "delay_for_gh" attribute if any to delay the job for X seconds
                self.delayed_until.hset(compute_delayed_until(delayed_for=self.delay_for_gh))

            else:
                # check the first available gh
                if permission == 'self':
                    if args:
                        try:
                            token = Token.get(token=args['access_token'])
                        except Token.DoesNotExist:
                            token = Token.get(username=args['username'])
                elif repository:
                    token = Token.get_one_for_repository(repository.pk, permission, available=False, sort_by='rate_limit_reset')
                else:
                    token = Token.get_one(available=False, sort_by='rate_limit_reset')

                # if we have a token, get it's delay before availability, and
                # set it on the job for future use
                if token:

                    remaining = token.get_remaining_seconds()
                    if remaining is not None and remaining >= 0:
                        self.delayed_until.hset(compute_delayed_until(remaining))
                    else:
                        self.delayed_until.delete()

                    self.gh = token.gh

                else:
                    # no token at all ? we may have no one for this permission !
                    # so retry in 15mn
                    self.delayed_until.hset(compute_delayed_until(delayed_for=60 * 15))

            return None

        # save it in the job, useful when cloning to avoid searching for a new
        # gh (will only happen if it is not available anymore)
        self.gh = token.gh

        # and ok, return it
        return token.gh

    def _set_gh(self, gh):
        """
        Set the arguments for the Connection object of the job from the given one
        """
        username = gh._connection_args['username']
        access_token = gh._connection_args['access_token']
        self.gh_args.hmset(username=username, access_token=access_token)

    # property to get/set "self.gh"
    gh = property(_get_gh, _set_gh)

    @property
    def gh_user(self):
        """
        Return the user used to make the connection
        """
        return GithubUser.objects.get(username=self.gh_args.hget('username'))

    def clone(self, priority=0, delayed_for=None, delayed_until=None, **force_fields):
        """
        Create a copy of the current job, copying the fiels defined in
        self.clonable_fields, possibly overriden by ones passed in force_fields.
        The job is then queued/delayed depending on delayed_for and delayed_until
        """
        clone_gh = 'gh' in self.clonable_fields
        if clone_gh:
            self.clonable_fields = list(self.clonable_fields)
            self.clonable_fields.remove('gh')

        instancehash_fields = [f for f in self.clonable_fields
                    if isinstance(getattr(self, f), fields.InstanceHashField)]
        if instancehash_fields:
            instancehash_values = self.hmget(*instancehash_fields)
            new_job_args = {k: v for k, v
                                in zip(instancehash_fields, instancehash_values)
                                if v is not None}
        else:
            new_job_args = {}

        for field in set(self.clonable_fields).difference(instancehash_fields):
            value = getattr(self, field).proxy_get()
            if value is not None:
                new_job_args[field] = value

        if clone_gh and 'gh' not in force_fields:
            try:
                new_job_args['gh'] = self.gh
            except:
                pass

        new_job_args.update(force_fields)

        # and add the job
        new_job = self.__class__.add_job(
                    identifier=self.identifier.hget(),
                    priority=priority,
                    delayed_for=delayed_for,
                    delayed_until=delayed_until,
                    **new_job_args
                )

        return new_job


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
