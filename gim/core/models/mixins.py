__all__ = []


class WithRepositoryMixin(object):
    """
    A base class for all models containing data owned by a repository.
    """

    def fetch(self, gh, defaults=None, force_fetch=False, parameters=None,
                                                        meta_base_name=None):
        """
        Enhance the default fetch by setting the current repository as
        default value.
        """
        if self.repository_id:
            if not defaults:
                defaults = {}
            defaults.setdefault('fk', {})['repository'] = self.repository
            defaults.setdefault('related', {}).setdefault('*', {}).setdefault('fk', {})['repository'] = self.repository

        return super(WithRepositoryMixin, self).fetch(gh, defaults,
                                               force_fetch=force_fetch,
                                               parameters=parameters,
                                               meta_base_name=meta_base_name)

    def defaults_create_values(self):
        return {'fk': {'repository': self.repository}}


class WithIssueMixin(WithRepositoryMixin):
    """
    A base class for all models containing data owned by an issue.
    """

    def fetch(self, gh, defaults=None, force_fetch=False, parameters=None,
                                                        meta_base_name=None):
        """
        Enhance the default fetch by setting the current repository and issue as
        default values.
        """
        if self.issue_id:
            if not defaults:
                defaults = {}
            defaults.setdefault('fk', {})['issue'] = self.issue
            defaults.setdefault('related', {}).setdefault('*', {}).setdefault('fk', {})['issue'] = self.issue

        return super(WithIssueMixin, self).fetch(gh, defaults,
                                               force_fetch=force_fetch,
                                               parameters=parameters,
                                               meta_base_name=meta_base_name)

    def defaults_create_values(self):
        values = super(WithIssueMixin, self).defaults_create_values()
        values['fk']['issue'] = self.issue
        return values


class WithCommitMixin(WithRepositoryMixin):
    """
    A base class for all models containing data owned by a commit.
    """

    def fetch(self, gh, defaults=None, force_fetch=False, parameters=None,
                                                        meta_base_name=None):
        """
        Enhance the default fetch by setting the current repository and issue
        commit as default values.
        """
        if self.commit_id:
            if not defaults:
                defaults = {}
            defaults.setdefault('fk', {})['commit'] = self.commit
            defaults.setdefault('related', {}).setdefault('*', {}).setdefault('fk', {})['commit'] = self.commit

        return super(WithCommitMixin, self).fetch(gh, defaults,
                                               force_fetch=force_fetch,
                                               parameters=parameters,
                                               meta_base_name=meta_base_name)

    def defaults_create_values(self):
        values = super(WithCommitMixin, self).defaults_create_values()
        values['fk']['commit'] = self.commit
        return values
