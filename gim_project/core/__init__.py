from threading import local

from limpyd.contrib.database import PipelineDatabase

from django.conf import settings

GITHUB_HOST = 'https://github.com/'


def get_main_limpyd_database():
    thread_data = local()
    if not hasattr(thread_data, 'main_limpyd_database'):
        thread_data.main_limpyd_database = PipelineDatabase(**settings.LIMPYD_DB_CONFIG)
    return thread_data.main_limpyd_database
