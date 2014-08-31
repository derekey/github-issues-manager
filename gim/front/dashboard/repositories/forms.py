import re

from django import forms
from django.core import validators

from gim.front.mixins.forms import LinkedToUserFormMixin

from gim.subscriptions.models import WaitingSubscription, Subscription


class ToggleRepositoryBaseForm(LinkedToUserFormMixin, forms.Form):
    """
    Base form to use to add/remove a repository
    """
    # allow foo/bar but also a full github url
    RE_REPO = re.compile('^(?:https?://(?:www.)?github\.com/)?\s*([\w\-\.]+)\s*/\s*([\w\-\.]+)(?:$|\s*|/)?')

    name = forms.CharField(
                validators=[
                    validators.RegexValidator(RE_REPO),
                ],
                error_messages={
                    'required': 'No repository given',
                    'invalid': 'Invalid repository name'
                },
                widget=forms.HiddenInput
            )

    repo_full_name = None

    def clean_name(self):
        """
        Return spaces in name, if for example copied from the github page:
        " foo / bar "
        """
        name = self.cleaned_data.get('name')
        if name:
            name = '/'.join(self.RE_REPO.match(name).groups())
        if '..' in name:
            raise forms.ValidationError('What are you trying to do ? ;)')
        self.repo_full_name = name
        return name

    def split_name(self, name):
        """
        Return the both part of the repository name: owner's username and
        repository's name
        """
        return name.split('/')

    def get_main_error_message(self):
        """
        Returns a main error message to use in a view: the one attached to the
        "name" field if any, or the one attached to the form. If there is
        errors but nor on the "name" field, neither on the form, use a default
        message.
        Returns None if there is no errors.
        """
        if not self.errors:
            return None
        return self.errors.get('name',
                    self.errors.get('__all__',
                        ['Unexpected error']
                    )
                )[0]


class AddRepositoryForm(ToggleRepositoryBaseForm):

    can_use = None

    def clean(self):
        """
        Check that the user can access the form's repository
        """
        cleaned_data = super(AddRepositoryForm, self).clean()
        name = cleaned_data.get('name', None)
        if name:
            # already a waiting subscription: can add only if fetch failed
            try:
                waiting_subscription = self.user.waiting_subscriptions.get(repository_name=name)
            except WaitingSubscription.DoesNotExist:
                pass
            else:
                if not waiting_subscription.can_add_again():
                    raise forms.ValidationError('You already added this repository. '
                                                'Processing is ongoing.')

            # already a subscription: cannot add
            owner_username, repository__name = self.split_name(name)
            if self.user.subscriptions.filter(
                        repository__owner__username=owner_username,
                        repository__name=repository__name
                    ).exists():
                raise forms.ValidationError('You already added this repository.')

            # does the user can use this repo ?
            self.can_use = self.user.can_use_repository(name)
            if self.can_use is None:
                raise forms.ValidationError('Cannot check if you are allowed '
                                            'to subscribe to this repository')
            elif not self.can_use:
                raise forms.ValidationError('You are not allowed to subscribe '
                                            'to this repository (maybe it does '
                                            'not exist ?)')

        return cleaned_data


class RemoveRepositoryForm(ToggleRepositoryBaseForm):

    subscription = None

    def clean(self):
        """
        Check that the user can remove the form's repository
        """
        cleaned_data = super(RemoveRepositoryForm, self).clean()
        name = cleaned_data.get('name', None)
        if name:
            self.subscription = None

            # do we have a waiting subscription ?
            try:
                self.subscription = self.user.waiting_subscriptions.get(
                                                        repository_name=name)
            except WaitingSubscription.DoesNotExist:
                pass

            # or a real subscription ?
            if not self.subscription:
                owner_username, repository__name = self.split_name(name)
                try:
                    self.subscription = self.user.subscriptions.get(
                                repository__owner__username=owner_username,
                                repository__name=repository__name
                            )
                except Subscription.DoesNotExist:
                    pass

            if not self.subscription:
                raise forms.ValidationError('There is no such repository to '
                                            'remove.')

        return cleaned_data
