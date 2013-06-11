from django.db import models

from extended_choices import Choices

from core.models import GithubUser, Repository

WAITING_SUBSCRIPTION_STATES = Choices(
    ('WAITING', 1, 'Waiting'),
    ('FETCHING', 2, 'Fetching'),
    ('FAILED', 3, 'Adding failed'),
)


class WaitingSubscription(models.Model):
    user = models.ForeignKey(GithubUser, related_name='waiting_subscriptions')
    repository_name = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_admin = models.BooleanField(default=False)
    state = models.PositiveSmallIntegerField(
        choices=WAITING_SUBSCRIPTION_STATES.CHOICES,
        default=WAITING_SUBSCRIPTION_STATES.WAITING)

    class Meta:
        unique_together = [('user', 'repository_name'), ]

    def __unicode__(self):
        return u'%s for %s (%s)' % (self.repository_name,
                                    self.user.username,
                                    self.get_state_display())

    @property
    def repository(self):
        """
        Property to return the repository matching the repository_name field.
        Raise a DoesNotExist if no repository found
        """
        owner_username, repository_name = self.repository_name.split('/')
        return Repository.objects.get(
            owner__username=owner_username,
            name=repository_name
        )

    def convert(self):
        """
        Convert the waiting subscription into a real one.
        The repository matching he repository_name field must exist.
        """
        if self.state in (WAITING_SUBSCRIPTION_STATES.FAILED,):
            raise Exception('Cannot convert a failed waiting subscription')

        owner_username, repository_name = self.repository_name.split('/')
        subscription, _ = Subscription.objects.get_or_create(
            user=self.user,
            repository=self.repository
        )
        subscription.state = SUBSCRIPTION_STATES.ADMIN if self.is_admin else SUBSCRIPTION_STATES.SIMPLE
        subscription.save()

        self.delete()


SUBSCRIPTION_STATES = Choices(
    ('SIMPLE', 1, 'User'),
    ('ADMIN', 2, 'Admin'),
    ('NORIGHTS', 3, 'No rights'),
)


class Subscription(models.Model):
    user = models.ForeignKey(GithubUser, related_name='subscriptions')
    repository = models.ForeignKey(Repository, related_name='subscriptions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    state = models.PositiveSmallIntegerField(
        choices=SUBSCRIPTION_STATES.CHOICES,
        default=SUBSCRIPTION_STATES.SIMPLE)

    class Meta:
        unique_together = [('user', 'repository'), ]
        index_together = [('user', 'state'), ]

    def __unicode__(self):
        return u'%s for %s (%s)' % (self.repository.name,
                                    self.user.username,
                                    self.get_state_display())
