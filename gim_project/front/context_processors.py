from datetime import datetime

from django.conf import settings


def default_context_data(request):
    return {
        'brand': {
            'short_name': settings.BRAND_SHORT_NAME,
            'long_name': settings.BRAND_LONG_NAME,
        },
        'utcnow': datetime.utcnow(),
    }
