import re

from django import forms
from django.core import validators


class AddRepositoryForm(forms.Form):
        
    name = forms.CharField(
                validators=[
                    validators.RegexValidator(re.compile('^[\w\-\.]+/[\w\-\.]+$')),
                ],
                error_messages={
                    'required': 'No repository given',
                    'invalid': 'Invalid repository name'
                },
                widget=forms.HiddenInput
            )

    def __init__(self, *args, **kwargs):
        """
        A user must be passed in kwargs.
        """
        self.user = kwargs.pop('user')
        super(AddRepositoryForm, self).__init__(*args, **kwargs)

    def clean(self):
        """
        Check that the user can access the form's repository
        """
        cleaned_data = super(AddRepositoryForm, self).clean()
        name = cleaned_data.get('name', None)
        if name:
            can_use = self.user.can_use_repository(name)
            if can_use is None:
                raise forms.ValidationError('Cannot check if you are allowed '
                                            'to work on this repository')
            elif not can_use:
                raise forms.ValidationError('You are not allowed to work on '
                                            'this repository (or it has no '
                                            'issues)')

        return cleaned_data

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
                    self.errors.get('__all', 
                        ['Unexpected error']
                    )
                )[0]
