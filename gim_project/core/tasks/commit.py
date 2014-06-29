# -*- coding: utf-8 -*-

__all__ = [
    'FetchCommitBySha',
]

from datetime import datetime

from limpyd import fields
from limpyd_jobs import STATUSES


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
    fetch_comments = fields.InstanceHashField()

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

        force_fetch = self.force_fetch.hget() == '1'
        fetch_comments = self.fetch_comments.hget() == '1'

        try:
            commit = repository.commits.filter(sha=sha)[0]
        except (Commit.DoesNotExist, IndexError):
            commit = Commit(repository=repository, sha=sha)
        else:
            if not force_fetch and commit.fetched_at:
                # a commit doesn't change so is we already have it, fetch it
                # only if we forced it
                self.status.hset(STATUSES.CANCELED)
                return None

        try:
            if fetch_comments:
                commit.fetch_all(gh, force_fetch=force_fetch)
            else:
                commit.fetch(gh, force_fetch=force_fetch)
        except ApiNotFoundError:
            # the commit doesn't exist anymore, delete it
            if commit.pk:
                commit.deleted = True
                commit.fetched_at = datetime.utcnow()
                commit.save(update_fields=['deleted', 'fetched_at'])
            self.deleted.hset(1)
            return False

        return True

    def success_message_addon(self, queue, result):
        if result is False:
            return ' [deleted]'
