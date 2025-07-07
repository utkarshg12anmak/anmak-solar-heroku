import os
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

# ─── Base directory ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ─── Read local .env if it exists ───────────────────────────────────────────
env = environ.Env(
    DEBUG=(bool, False),
    DJANGO_ENV=(str, 'prod'),
)
env_file = BASE_DIR / '.env.local2'
if env_file.exists():
    env.read_env(str(env_file))


# ─── Core settings ───────────────────────────────────────────────────────────
SECRET_KEY = env('DJANGO_SECRET_KEY')  # raises error if not set
DEBUG      = env('DEBUG')
DJANGO_ENV = env('DJANGO_ENV').lower()
ALLOWED_HOSTS = env.list(
    'ALLOWED_HOSTS',
    default=['localhost', '127.0.0.1']
)


# ─── Database ────────────────────────────────────────────────────────────────
DATABASES = {
    'default': env.db_url(
        'DATABASE_URL',
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
    )
}


# ─── Static files (CSS, JavaScript, Images) ─────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = (
    'whitenoise.storage.CompressedManifestStaticFilesStorage'
)


# ─── AWS S3 (for Media) ──────────────────────────────────────────────────────
AWS_ACCESS_KEY_ID     = env('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY')
AWS_S3_REGION_NAME    = env('AWS_S3_REGION_NAME', default='eu-central-1')
AWS_BUCKET_DEV        = env('AWS_BUCKET_DEV')
AWS_BUCKET_PROD       = env('AWS_BUCKET_PROD')
AWS_STORAGE_BUCKET_NAME = (
    AWS_BUCKET_PROD if DJANGO_ENV == 'prod' else AWS_BUCKET_DEV
)
AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
AWS_DEFAULT_ACL      = None
AWS_QUERYSTRING_AUTH = False
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',
}
DEFAULT_FILE_STORAGE = 'oms_project.storage_backends.MediaStorage'
MEDIA_URL  = f"https://{AWS_S3_CUSTOM_DOMAIN}/"
MEDIA_ROOT = BASE_DIR / 'media'


# ─── Application definition ─────────────────────────────────────────────────
INSTALLED_APPS = [
    # Django core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    # Third-party
    'widget_tweaks',
    'storages',
    'django_crontab',
    "simple_history",
]

# Only add debug_toolbar in DEBUG mode
if DEBUG:
    INSTALLED_APPS.append('debug_toolbar')


# Your apps
INSTALLED_APPS += [
    'leads',
    'customers',
    'profiles',
    'expenses',
    'interests',
    'items',
    'visit_details',
    'reminders',
    'quotes',
    'core.apps.CoreConfig',
    'initial_setup.apps.InitialSetupConfig',
]


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ─── Middleware ─────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.middleware.LoginRequiredMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',    
    "simple_history.middleware.HistoryRequestMiddleware",
]

if DEBUG:
    # Debug Toolbar should be first
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')


# ─── URL Configuration ──────────────────────────────────────────────────────
ROOT_URLCONF = 'oms_project.urls'


# ─── Templates ──────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages', 
            ],
        },
    },
]


# ─── WSGI ───────────────────────────────────────────────────────────────────
WSGI_APPLICATION = 'oms_project.wsgi.application'


# ─── Authentication redirects ────────────────────────────────────────────────
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'
LOGIN_URL          = 'login'


# ─── Password validation ─────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'UserAttributeSimilarityValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.MinimumLengthValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'CommonPasswordValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'NumericPasswordValidator'
        ),
    },
]


# ─── Internationalization ────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Asia/Kolkata'
USE_I18N      = True
USE_L10N      = True
USE_TZ        = True


# ─── Logging ────────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG' if DEBUG else 'INFO',
    },
}


# ─── Debug Toolbar (only if DEBUG) ──────────────────────────────────────────
if DEBUG:
    INTERNAL_IPS = ['127.0.0.1']
    DEBUG_TOOLBAR_PANELS = [
        'debug_toolbar.panels.history.HistoryPanel',        # request history & snapshots
        'debug_toolbar.panels.versions.VersionsPanel',      # Python, Django & app versions
        'debug_toolbar.panels.timer.TimerPanel',            # request timing breakdown
        'debug_toolbar.panels.settings.SettingsPanel',      # your Django settings
        'debug_toolbar.panels.headers.HeadersPanel',        # HTTP & WSGI headers
        'debug_toolbar.panels.request.RequestPanel',        # GET/POST/Cookie/Session
        'debug_toolbar.panels.sql.SQLPanel',                # SQL queries + EXPLAIN links
        'debug_toolbar.panels.staticfiles.StaticFilesPanel',# which static files were served
        'debug_toolbar.panels.templates.TemplatesPanel',    # templates used & context
        'debug_toolbar.panels.alerts.AlertsPanel',          # HTML form/alert warnings
        'debug_toolbar.panels.cache.CachePanel',            # cache hits, misses & calls
        'debug_toolbar.panels.signals.SignalsPanel',        # signals sent & receivers
        'debug_toolbar.panels.redirects.RedirectsPanel',    # intercept & inspect redirects
        'debug_toolbar.panels.profiling.ProfilingPanel',    # function-level profiling
    ]


CRONJOBS = [
    # (cron-schedule, management-command, [optional args])
    ('0 4 * * *', 'django.core.management.call_command', ['clearsessions']),
]

DEBUG_TOOLBAR_CONFIG = {
  'SHOW_COLLAPSED': True,              # start panels collapsed
  'ENABLE_STACKTRACES': True,          # include Python stacktraces for SQL and templates
  'RESULTS_CACHE_SIZE': 100,           # how many requests to keep in HistoryPanel
  'SHOW_TEMPLATE_CONTEXT': True,       # surface full template context in the TemplatesPanel
}


import os

# Heroku puts chrome at this path:
if os.environ.get('GOOGLE_CHROME_BIN'):
    PYPPETEER_CHROME_PATH = os.environ['GOOGLE_CHROME_BIN']
