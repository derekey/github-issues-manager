# Django settings for gim_project project.

import os.path
import logging
from django.core.urlresolvers import reverse_lazy

DJANGO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

MANAGERS = ADMINS

INTERNAL_IPS = ('127.0.0.1',)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',  # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': os.path.normpath(os.path.join(DJANGO_ROOT, 'gim.db')),                      # Or path to database file if using sqlite3.
        # The following settings are not used with sqlite3:
        'USER': '',
        'PASSWORD': '',
        'HOST': '',                      # Empty for localhost through domain sockets or '127.0.0.1' for localhost through TCP.
        'PORT': '',                      # Set to empty string for default.
    }
}

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
STATIC_ROOT = os.path.normpath(os.path.join(DJANGO_ROOT, '..', 'static/'))

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
    'front.middleware.AddMessagesToAjaxResponseMiddleware',
    'async_messages.middleware.AsyncMiddleware',
    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'gim_project.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'gim_project.wsgi.application'

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
    "front.context_processors.default_context_data",
)


AUTH_USER_MODEL = 'core.GithubUser'

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',
    # Uncomment the next line to enable the admin:
    # 'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    # 'django.contrib.admindocs',

    'south',

    'jsonfield',
    'adv_cache_tag',
    'macros',

    'core',
    'subscriptions',

    'hooks',  # github hooks (push from github to isshub)
    'events',  # change events of issues (updated body, labels...)
    'graphs',  # graph of repositories...
    'activity',  # activity (timeline, updates...)

    'front',
    'front.auth',

    'front.activity',

    'front.dashboard',
    'front.dashboard.repositories',

    'front.repository',
    'front.repository.issues',
    'front.repository.dashboard',
    'front.repository.board',
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
    'front.auth.backends.GithubBackend',
)

LOGIN_URL = reverse_lazy('front:auth:login')

GITHUB_SCOPE = 'repo'

WORKERS_LOGGER_CONFIG = {
    'handler': logging.StreamHandler(),
    'level': logging.INFO
}

try:
    from local_conf import conf
except ImportError:
    conf = {}

# define settings below in local_conf.py, in a "conf" dictionnary
# SECRET_KEY, GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET **MUST** be defined

SECRET_KEY = conf['SECRET_KEY']

DEBUG = conf.get('DEBUG', True)
TEMPLATE_DEBUG = DEBUG

ALLOWED_HOSTS = conf.get('ALLOWED_HOSTS', [])

GITHUB_CLIENT_ID = conf['GITHUB_CLIENT_ID']
GITHUB_CLIENT_SECRET = conf['GITHUB_CLIENT_SECRET']

GITHUB_HOOK_URL = conf.get('GITHUB_HOOK_URL', None)

DATABASES = {  # default to a sqlite db "gim.db"
    'default': {
        'ENGINE': conf.get('DB_ENGINE', 'django.db.backends.sqlite3'),
        'NAME': conf.get('DB_NAME', os.path.normpath(os.path.join(DJANGO_ROOT, '..', 'gim.db'))),
        'USER': conf.get('DB_USER', ''),
        'PASSWORD': conf.get('DB_PASSWORD', ''),
        'HOST': conf.get('DB_HOST', ''),
        'PORT': conf.get('DB_PORT', ''),
    }
}

LIMPYD_DB_CONFIG = {
    'host': conf.get('LIMPYD_DB_HOST', 'localhost'),
    'port': conf.get('LIMPYD_DB_PORT', 6379),
    'db': conf.get('LIMPYD_DB_HOST', 0),
}

WORKERS_REDIS_CONFIG = LIMPYD_DB_CONFIG


CACHES = {
    'default': {
        'BACKEND': 'redis_cache.cache.RedisCache',
        'LOCATION': '%s:%d:%d' % (
                conf.get('CACHE_DEFAULT_HOST', 'localhost'),
                conf.get('CACHE_DEFAULT_PORT', 6379),
                conf.get('CACHE_DEFAULT_DB', 1),
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
                conf.get('CACHE_ISSUES_TAG_HOST', 'localhost'),
                conf.get('CACHE_ISSUES_TAG_PORT', 6379),
                conf.get('CACHE_ISSUES_TAG_DB', 2),
            ),
        'OPTIONS': {
            'CLIENT_CLASS': 'redis_cache.client.DefaultClient',
            'PARSER_CLASS': 'redis.connection.HiredisParser',
            'PICKLE_VERSION': 2,
        }
    },
}

BRAND_SHORT_NAME = conf.get('BRAND_SHORT_NAME', 'G.I.M')
BRAND_LONG_NAME = conf.get('BRAND_LONG_NAME', 'Github Issues Manager')

DEBUG_TOOLBAR = False
try:
    from local_settings import *
except ImportError:
    pass
else:
    if DEBUG_TOOLBAR:
        INSTALLED_APPS += ('debug_toolbar', 'template_timings_panel', )
        MIDDLEWARE_CLASSES += ('debug_toolbar.middleware.DebugToolbarMiddleware', )
