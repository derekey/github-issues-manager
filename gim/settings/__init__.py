# Django settings for gim project.


import json
import os.path
import logging

from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse_lazy

SETTINGS_PATH = os.path.dirname(os.path.abspath(__file__))
GIM_ROOT = os.path.normpath(os.path.join(SETTINGS_PATH, '..'))

DEBUG = False
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

MANAGERS = ADMINS

INTERNAL_IPS = ('127.0.0.1',)

# Hosts/domain names that are valid for this site; required if DEBUG is False
# See https://docs.djangoproject.com/en/1.5/ref/settings/#allowed-hosts
ALLOWED_HOSTS = []

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# In a Windows environment this must be set to your system time zone.
TIME_ZONE = 'UTC'

DATE_FORMAT = "N j, Y"  # Aug. 6, 2012.
DATETIME_FORMAT = "N j, Y P"  # Aug. 6, 2012 1:55 p.m.

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = False

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/var/www/example.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://example.com/media/", "http://media.example.com/"
MEDIA_URL = ''

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/var/www/example.com/static/"
STATIC_ROOT = os.path.normpath(os.path.join(GIM_ROOT, 'static/'))

# URL prefix for static files.
# Example: "http://example.com/static/", "http://static.example.com/"
STATIC_URL = '/static/'

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.CachedStaticFilesStorage'

# Make this unique, and don't share it with anybody.

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    ('django.template.loaders.cached.Loader', (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.Loader',
    )),
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'gim.front.middleware.AddMessagesToAjaxResponseMiddleware',
    'async_messages.middleware.AsyncMiddleware',
    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'gim.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'gim.wsgi.application'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

TEMPLATE_CONTEXT_PROCESSORS = (
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "django.core.context_processors.static",
    "django.core.context_processors.tz",
    "django.contrib.messages.context_processors.messages",
    "gim.front.context_processors.default_context_data",
)


AUTH_USER_MODEL = 'core.GithubUser'

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',
    # Uncomment the next line to enable the admin:
    'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    # 'django.contrib.admindocs',

    'south',

    'jsonfield',
    'adv_cache_tag',
    'macros',

    'gim.core',
    'gim.subscriptions',

    'gim.hooks',  # github hooks (push from github to isshub)
    'gim.events',  # change events of issues (updated body, labels...)
    'gim.graphs',  # graph of repositories...
    'gim.activity',  # activity (timeline, updates...)

    'gim.front',
    'gim.front.auth',

    'gim.front.activity',

    'gim.front.dashboard',
    'gim.front.dashboard.repositories',

    'gim.front.repository',
    'gim.front.repository.issues',
    'gim.front.repository.dashboard',
    'gim.front.repository.board',
)

DEBUG_TOOLBAR_PANELS = [
    'debug_toolbar.panels.versions.VersionsPanel',
    'debug_toolbar.panels.timer.TimerPanel',
    'debug_toolbar.panels.settings.SettingsPanel',
    'debug_toolbar.panels.headers.HeadersPanel',
    'debug_toolbar.panels.request.RequestPanel',
    'debug_toolbar.panels.sql.SQLPanel',
    'debug_toolbar.panels.staticfiles.StaticFilesPanel',
    'debug_toolbar.panels.templates.TemplatesPanel',
    'debug_toolbar.panels.cache.CachePanel',
    'debug_toolbar.panels.signals.SignalsPanel',
    'debug_toolbar.panels.logging.LoggingPanel',
    'debug_toolbar.panels.redirects.RedirectsPanel',
    # 'template_timings_panel.panels.TemplateTimings.TemplateTimings',
]


DEBUG_TOOLBAR_CONFIG = {
    'INTERCEPT_REDIRECTS': False,
}

SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['mail_admins', 'console'],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}


AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'gim.front.auth.backends.GithubBackend',
)

LOGIN_URL = reverse_lazy('front:auth:login')

GITHUB_SCOPE = 'repo'

WORKERS_LOGGER_CONFIG = {
    'handler': logging.StreamHandler(),
    'level': logging.INFO
}


secrets = {}
if 'SECRETS_PATH' in os.environ:
    with open(os.environ['SECRETS_PATH']) as f:
        secrets = json.loads(f.read())


def get_env_variable(var_name, default=None):
    try:
        return os.environ[var_name]
    except KeyError:
        try:
            return secrets[var_name]
        except KeyError:
            if default is not None:
                return default
            msg = "Set the %s environment variable"
            error_msg = msg % var_name
            raise ImproperlyConfigured(error_msg)


# define settings below in env or file defined by SECRETS_PATH
# SECRET_KEY, GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET **MUST** be defined

SECRET_KEY = get_env_variable('DJANGO_SECRET_KEY')

ALLOWED_HOSTS = get_env_variable('ALLOWED_HOSTS', [])
if isinstance(ALLOWED_HOSTS, basestring):
    # if got from json, it's already a list, but not from env
    ALLOWED_HOSTS = ALLOWED_HOSTS.split(',')

GITHUB_CLIENT_ID = get_env_variable('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET = get_env_variable('GITHUB_CLIENT_SECRET')

GITHUB_HOOK_URL = get_env_variable('GITHUB_HOOK_URL', None)

DATABASES = {  # default to a sqlite db "gim.db"
    'default': {
        'ENGINE': get_env_variable('DB_ENGINE', 'django.db.backends.sqlite3'),
        'NAME': get_env_variable('DB_NAME', os.path.normpath(os.path.join(GIM_ROOT, '..', 'db', 'gim.db'))),
        'USER': get_env_variable('DB_USER', ''),
        'PASSWORD': get_env_variable('DB_PASSWORD', ''),
        'HOST': get_env_variable('DB_HOST', ''),
        'PORT': get_env_variable('DB_PORT', ''),
        'CONN_MAX_AGE': get_env_variable('DB_CONN_MAX_AGE', 0),
    }
}

LIMPYD_DB_CONFIG = {
    'host': get_env_variable('LIMPYD_DB_REDIS_HOST', 'localhost'),
    'port': int(get_env_variable('LIMPYD_DB_REDIS_PORT', 6379)),
    'db': int(get_env_variable('LIMPYD_DB_REDIS_DB', 0)),
}

WORKERS_REDIS_CONFIG = {
    'host': get_env_variable('LIMPYD_JOBS_REDIS_HOST', 'localhost'),
    'port': int(get_env_variable('LIMPYD_JOBS_REDIS_PORT', 6379)),
    'db': int(get_env_variable('LIMPYD_JOBS_REDIS_DB', 0)),
}


CACHES = {
    'default': {
        'BACKEND': 'redis_cache.cache.RedisCache',
        'LOCATION': '%s:%d:%d' % (
                get_env_variable('CACHE_DEFAULT_REDIS_HOST', 'localhost'),
                int(get_env_variable('CACHE_DEFAULT_REDIS_PORT', 6379)),
                int(get_env_variable('CACHE_DEFAULT_REDIS_DB', 1)),
            ),
        'TIMEOUT': 30*24*60*60,  # 30 days
        'OPTIONS': {
            'CLIENT_CLASS': 'redis_cache.client.DefaultClient',
            'PARSER_CLASS': 'redis.connection.HiredisParser',
            'PICKLE_VERSION': 2,
        }
    },
    'issues_tag': {
        'BACKEND': 'redis_cache.cache.RedisCache',
        'LOCATION': '%s:%d:%d' % (
                get_env_variable('CACHE_ISSUES_TAG_REDIS_HOST', 'localhost'),
                int(get_env_variable('CACHE_ISSUES_TAG_REDIS_PORT', 6379)),
                int(get_env_variable('CACHE_ISSUES_TAG_REDIS_DB', 2)),
            ),
        'OPTIONS': {
            'CLIENT_CLASS': 'redis_cache.client.DefaultClient',
            'PARSER_CLASS': 'redis.connection.HiredisParser',
            'PICKLE_VERSION': 2,
        }
    },
}

BRAND_SHORT_NAME = get_env_variable('BRAND_SHORT_NAME', 'G.I.M')
BRAND_LONG_NAME = get_env_variable('BRAND_LONG_NAME', 'Github Issues Manager')

FAVICON_PATH = get_env_variable('FAVICON_PATH', None)
FAVICON_STATIC_MANAGED = get_env_variable('FAVICON_STATIC_MANAGED', True)

DEBUG_TOOLBAR = False
try:
    from .local_settings import *
except ImportError:
    pass
else:
    if DEBUG_TOOLBAR:
        INSTALLED_APPS += ('debug_toolbar', 'template_timings_panel', )
        MIDDLEWARE_CLASSES += ('debug_toolbar.middleware.DebugToolbarMiddleware', )
