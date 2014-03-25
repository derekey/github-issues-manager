class JobRegistry(set):

    @property
    def classes(self):
        return self

JobRegistry = JobRegistry()


from .comment import *
from .event import *
from .githubuser import *
from .issue import *
from .label import *
from .milestone import *
from .repository import *
from .tokens import *
