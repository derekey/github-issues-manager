from django.conf import settings

from limpyd import fields
from limpyd.contrib.database import PipelineDatabase
from limpyd_jobs.models import BaseJobsModel, Job as LimpydJob
from limpyd_jobs.workers import Worker as LimpydWorker, logger

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
        if 'job_model' in kwargs and hasattr(kwargs['job_model'], 'queue_name'):
            self.name = kwargs['job_model'].queue_name
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

    def run(self, queue):
        return None

    def on_success(self, queue, result):
        return None

    def success_message_addon(self, queue, result):
        return ''

    @classmethod
    def add_job(cls, identifier, priority=0, queue_model=None, prepend=False, **fields_if_new):
        return super(Job, cls).add_job(identifier, cls.queue_name, priority, queue_model, prepend, **fields_if_new)



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


class UserJob(DjangoModelJob):
    """
    Abstract job model for jobs based on the GithubUser model
    """
    abstract = True
    model = GithubUser


class UserFetchAvailableRepositoriesJob(UserJob):
    """
    Job that fetches available repositories of a user
    """
    queue_name = 'fetch-avaiable-repos'

    nb_repos = fields.InstanceHashField()
    nb_orgs = fields.InstanceHashField()

    def run(self, queue):
        """
        Get the user and its available repositories from github
        """
        super(UserFetchAvailableRepositoriesJob, self).run(queue)
        user = self.get_django_object_from_identifier()
        result = user.fetch_available_repositories()
        return result

    def on_success(self, queue, result):
        """
        Save infos got from the fetch_available_repositories call
        """
        nb_repos, nb_orgs = result
        self.hmset(nb_repos=nb_repos, nb_orgs=nb_orgs)

    def success_message_addon(self, queue, result):
        """
        Display infos got from the fetch_available_repositories call
        """
        nb_repos, nb_orgs = result
        return ' [nb_repos=%d, nb_orgs=%d]' % (nb_repos, nb_orgs)
