
class LinkedToUserForm(object):
    def __init__(self, *args, **kwargs):
        """
        Get the "user" argument passed as parameter
        """
        self.user = kwargs.pop('user')
        super(LinkedToUserForm, self).__init__(*args, **kwargs)
