# -*- coding: utf-8 -*-

__all__ = [
    'FetchCommitBySha',
]

from limpyd import fields

from core.models import Repository, Commit
from core.ghpool import ApiNotFoundError

from .base import Job


class FetchCommitBySha(Job):
    """
    Fetch a commit in a repository, given only the commit's sha
    """
    queue_name = 'fetch-commit-by-sha'
    deleted = fields.InstanceHashField()
    force_fetch = fields.InstanceHashField()

    permission = 'read'

    @property
    def repository(self):
        if not hasattr(self, '_repository'):
            repository_id, sha = self.identifier.hget().split('#')
            self._repository = Repository.objects.get(id=repository_id)
        return self._repository

    def run(self, queue):
        """
        Fetch the commit with the given sha for the current repository
        """
        super(FetchCommitBySha, self).run(queue)

        gh = self.gh
        if not gh:
            return  # it's delayed !

        repository_id, sha = self.identifier.hget().split('#')

        repository = self.repository

        try:
            commit = repository.commits.filter(sha=sha)[0]
        except (Commit.DoesNotExist, IndexError):
            commit = Commit(repository=repository, sha=sha)

        force_fetch = self.force_fetch.hget() == '1'
        try:
            commit.fetch(gh, force_fetch=force_fetch)
        except ApiNotFoundError:
            # the commit doesn't exist anymore, delete it
            if commit.pk:
                commit.delete()
            self.deleted.hset(1)
            return False

        return True

    def success_message_addon(self, queue, result):
        if result is False:
            return ' [deleted]'
