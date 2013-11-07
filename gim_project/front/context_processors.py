from datetime import datetime


def default_context_data(request):
    return {
        'utcnow': datetime.utcnow(),
    }
