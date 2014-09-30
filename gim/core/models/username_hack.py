from django.db.models.signals import class_prepared
from django.core import validators


def longer_username(sender, *args, **kwargs):
    # http://stackoverflow.com/a/2613385
    # You can't just do `if sender == django.contrib.auth.models.User`
    # because you would have to import the model
    # You have to test using __name__ and __module__
    if sender.__name__ == "GithubUser" and sender.__module__ == "gim.core.models.users":
        field = sender._meta.get_field("username")
        field.max_length = 255
        field.validators = [v for v in field.validators if not isinstance(v, validators.RegexValidator)]


class_prepared.connect(longer_username)
