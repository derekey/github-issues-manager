from datetime import datetime

from django.conf import settings

from gim.core.models import GITHUB_STATUS_CHOICES


def default_context_data(request):
    return {
        'brand': {
            'short_name': settings.BRAND_SHORT_NAME,
            'long_name': settings.BRAND_LONG_NAME,
            'favicon': {
                'path': settings.FAVICON_PATH,
                'static_managed': settings.FAVICON_STATIC_MANAGED,
            },
        },
        'utcnow': datetime.utcnow(),
        'GITHUB_STATUSES': GITHUB_STATUS_CHOICES,
    }
