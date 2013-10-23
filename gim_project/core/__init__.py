from limpyd.contrib.database import PipelineDatabase

from django.conf import settings

GITHUB_HOST = 'https://github.com/'

main_limpyd_database = PipelineDatabase(**settings.LIMPYD_DB_CONFIG)
