from django import forms


class LinkedToUserFormMixin(object):
    """
    A simple mixin that get the "user" argument passed as parameter and save it
    in the "user" instance's attribute
    """
    user_attribute = 'user'

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super(LinkedToUserFormMixin, self).__init__(*args, **kwargs)
        attr = '%s_id' % self.user_attribute
        if self.user_attribute and getattr(self, 'instance', None) and hasattr(self.instance, attr):
            if not getattr(self.instance, attr):
                setattr(self.instance, self.user_attribute, self.user)


class LinkedToRepositoryFormMixin(forms.ModelForm):
    """
    A simple mixin that getthe "repository" argument passed as parameter and
    save it in the "repository" instance's attribute.
    Will also set the repository as attribute of the form's instance if there
    is any, unless "repository_attribute" is None
    """
    repository_attribute = 'repository'

    def __init__(self, *args, **kwargs):
        self.repository = kwargs.pop('repository')
        super(LinkedToRepositoryFormMixin, self).__init__(*args, **kwargs)
        attr = '%s_id' % self.repository_attribute
        if self.repository_attribute and getattr(self, 'instance', None) and hasattr(self.instance, attr):
            if not getattr(self.instance, attr):
                setattr(self.instance, self.repository_attribute, self.repository)

    def validate_unique(self):
        exclude = self._get_validation_exclusions()
        if exclude and 'repository' in exclude:
            exclude.remove('repository')
        try:
            self.instance.validate_unique(exclude=exclude)
        except forms.ValidationError as e:
            self._update_errors(e.message_dict)


class LinkedToIssueFormMixin(LinkedToRepositoryFormMixin):
    """
    A simple mixin that getthe "issue" argument passed as parameter and
    save it in the "issue" instance's attribute.
    Will also set the issue as attribute of the form's instance if there
    is any, unless "issue__attribute" is None
    Do the same the repository, as its a subclass of LinkedToRepositoryFormMixin
    """
    issue_attribute = 'issue'

    def __init__(self, *args, **kwargs):
        self.issue = kwargs.pop('issue')

        # pass the repository to the parent class
        kwargs['repository'] = self.issue.repository
        super(LinkedToIssueFormMixin, self).__init__(*args, **kwargs)

        attr = '%s_id' % self.issue_attribute
        if self.issue_attribute and getattr(self, 'instance', None) and hasattr(self.instance, attr):
            if not getattr(self.instance, attr):
                setattr(self.instance, self.issue_attribute, self.issue)

    def validate_unique(self):
        exclude = self._get_validation_exclusions()
        if exclude:
            if 'repository' in exclude:
                exclude.remove('repository')
            if 'issue' in exclude:
                exclude.remove('issue')
        try:
            self.instance.validate_unique(exclude=exclude)
        except forms.ValidationError as e:
            self._update_errors(e.message_dict)
