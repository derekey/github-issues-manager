from random import choice

from django.db import models

from async_messages import messages
from extended_choices import Choices

from core.models import GithubUser, Repository
from core.utils import contribute_to_model


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

    def convert(self, rights):
        """
        Convert the waiting subscription into a real one with the given rights
        (rights are "admin", "push", "read")
        The repository matching he repository_name field must exist.
        """
        if self.state == WAITING_SUBSCRIPTION_STATES.FAILED:
            raise Exception('Cannot convert a failed waiting subscription')

        if rights not in set(["admin", "push", "read"]):
            raise Exception('Cannot convert a subscription if not enough rights')

        owner_username, repository_name = self.repository_name.split('/')
        subscription, _ = Subscription.objects.get_or_create(
            user=self.user,
            repository=self.repository
        )
        subscription.state = SUBSCRIPTION_STATES.ADMIN if rights == "admin" \
                             else SUBSCRIPTION_STATES.USER if rights == "push" \
                             else SUBSCRIPTION_STATES.READ
        subscription.save()

        self.delete()


SUBSCRIPTION_STATES = Choices(
    ('READ', 1, 'Simple user'),  # can read
    ('USER', 2, 'Collaborator'),  # can push, create issues
    ('ADMIN', 3, 'Admin'),  # can admin, push, create issues
    ('NORIGHTS', 4, 'No rights'),  # no access
)
SUBSCRIPTION_STATES.ALL_RIGHTS = [s[0] for s in SUBSCRIPTION_STATES]
SUBSCRIPTION_STATES.READ_RIGHTS = [SUBSCRIPTION_STATES.READ, SUBSCRIPTION_STATES.USER, SUBSCRIPTION_STATES.ADMIN]
SUBSCRIPTION_STATES.WRITE_RIGHTS = [SUBSCRIPTION_STATES.USER, SUBSCRIPTION_STATES.ADMIN]


class Subscription(models.Model):
    user = models.ForeignKey(GithubUser, related_name='subscriptions')
    repository = models.ForeignKey(Repository, related_name='subscriptions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    state = models.PositiveSmallIntegerField(
        choices=SUBSCRIPTION_STATES.CHOICES,
        default=SUBSCRIPTION_STATES.READ)

    class Meta:
        unique_together = [('user', 'repository'), ]
        index_together = [('user', 'state'), ]

    def __unicode__(self):
        return u'%s for %s (%s)' % (self.repository.name,
                                    self.user.username,
                                    self.get_state_display())


class _Repository(models.Model):
    class Meta:
        abstract = True

    def has_subscriptions(self, states=SUBSCRIPTION_STATES.READ_RIGHTS):
        """
        Return True if the repository has at least one subscription with the
        given rights (by detault all reading&more rights)
        """
        return self.subscriptions.filter(state__in=states).exists()

contribute_to_model(_Repository, Repository)


class _GithubUser(models.Model):
    class Meta:
        abstract = True

    AUTHORIZED_RIGHTS = {
        SUBSCRIPTION_STATES.ADMIN: ('admin', ),
        SUBSCRIPTION_STATES.USER: ('admin', 'push', ),
        SUBSCRIPTION_STATES.READ: ('admin', 'push', 'pull', ),
    }

    MAX_RIGHT = {
        'admin': SUBSCRIPTION_STATES.ADMIN,
        'push': SUBSCRIPTION_STATES.USER,
        'pull': SUBSCRIPTION_STATES.READ,
        None: SUBSCRIPTION_STATES.NORIGHTS,
    }

    def check_subscriptions(self):
        """
        Check if subscriptions are still ok.
        If will use data from "available repositories" for the ones that are ok
        and will restrict rights for others
        """
        subs = {sub.repository.full_name: sub for sub in self.subscriptions.all()}
        avails = self.available_repositories_set.all().select_related('repository__owner')

        todo = set(subs.keys())
        downgraded = {}
        upgraded = {}

        # check from repositories officialy available for the user
        for avail in avails:
            name = avail.repository.full_name

            if name not in subs:
                continue

            todo.remove(name)

            sub = subs[name]
            max_right = self.MAX_RIGHT[avail.permission]

            # sub with no rights: upgrade if possible
            if sub.state == SUBSCRIPTION_STATES.NORIGHTS:
                if max_right != SUBSCRIPTION_STATES.NORIGHTS:
                    upgraded[name] = max_right

            # sub with rights but not on the avail: downgrade with no rights
            elif not avail.permission:
                downgraded[name] = SUBSCRIPTION_STATES.NORIGHTS

            # sub rights not in matchinng one for the avail rights: downgrade to max allowed
            elif avail.permission not in self.AUTHORIZED_RIGHTS[sub.state]:
                downgraded[name] = max_right

            # we have sufficient rigts, but try to upgrade them to max allowed
            elif max_right != sub.state:
                upgraded[name] = max_right

        # check subs that are not done (so, not in officially available ones)
        for name in todo:
            sub = subs[name]
            repo = sub.repository

            # repo owner by the user: ensure we have max rights
            if repo.owner_id == self.id:
                if sub.state != SUBSCRIPTION_STATES.ADMIN:
                    upgraded[name] = SUBSCRIPTION_STATES.ADMIN

            # private repo from another owner: it's not in availables, so no rights anymore
            elif repo.private:
                if sub.state != SUBSCRIPTION_STATES.NORIGHTS:
                    downgraded[name] = SUBSCRIPTION_STATES.NORIGHTS

            # public repo from another: it's not in availables, so read rights only
            elif sub.state not in (SUBSCRIPTION_STATES.READ, SUBSCRIPTION_STATES.NORIGHTS):
                downgraded[name] = SUBSCRIPTION_STATES.READ

        # continue if changes
        if upgraded or downgraded:
            message_content = []

            # apply changes
            for is_up, dikt in [(True, upgraded), (False, downgraded)]:
                by_state = {}
                for name, state in dikt.items():
                    sub = subs[name]
                    sub.state = state
                    sub.save(update_fields=['state'])
                    by_state.setdefault(sub.get_state_display(), []).append(name)

                # message for this kind: one li by change (change=[up|down]+new-state)
                message_content += ['<li>%s <strong>%s</strong> to: <strong>%s</strong></li>' % (
                                            'upgraded' if is_up else 'downgraded',
                                            ', '.join(repos),
                                            state,
                                        )
                                   for state, repos in by_state.items()]

            # prepare message
            message = 'Some rights have changed:<ul>%s</ul>' % ''.join(message_content)
            messages.info(self, message)

        return upgraded, downgraded


contribute_to_model(_GithubUser, GithubUser)
