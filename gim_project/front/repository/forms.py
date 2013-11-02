from django import forms


class LinkedToRepositoryForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        self.repository = kwargs.pop('repository')
        super(LinkedToRepositoryForm, self).__init__(*args, **kwargs)
        if not self.instance.repository_id:
            self.instance.repository = self.repository

    def validate_unique(self):
        """
        Calls the instance's validate_unique() method and updates the form's
        validation errors if any were raised.
        """
        exclude = self._get_validation_exclusions()
        if exclude and 'repository' in exclude:
            exclude.remove('repository')
        try:
            self.instance.validate_unique(exclude=exclude)
        except forms.ValidationError as e:
            self._update_errors(e.message_dict)
