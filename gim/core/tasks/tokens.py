__all__ = [
    'ResetTokenFlags',
]

from gim.core.limpyd_models import Token

from .base import Job


class ResetTokenFlags(Job):
    queue_name = 'reset-token-flags'

    @property
    def token_obj(self):
        if not hasattr(self, '_token_obj'):
            self._token_obj, _ = Token.get_or_connect(token=self.identifier.hget())
        return self._token_obj

    def run(self, queue):
        super(ResetTokenFlags, self).run(queue)

        return self.token_obj.reset_flags()

    def on_success(self, queue, result):
        if result is False:
            ttl = self.token_obj.connection.ttl(self.token_obj.rate_limit_remaining.key)
            self.clone(delayed_for=ttl+2)
