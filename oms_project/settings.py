import os
from pathlib import Path



# ─── OLD DEFINITIONS (REMOVE THESE!) ────────────────────────────────────────────
# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# ────────────────────────────────────────────────────────────────────────────────


BASE_DIR = Path(__file__).resolve().parent.parent

MEDIA_URL  = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STATIC_URL  = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

 # 3a) Tell Django to also look inside <BASE_DIR>/static/ when loading static files.
STATICFILES_DIRS = [
     BASE_DIR / "static",
]



USE_TZ = True
TIME_ZONE = 'Asia/Kolkata'

# ─── 4) Template directories ───────────────────────────────────────────────────
# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-*51yuzpyls+3q#n1w4!lyxyf4h3si=pb6($ovjheousnhn)+&j"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.contenttypes",
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.auth',
    'django.contrib.humanize',
    "core",
    "leads",
    'customers',
    'profiles',
    'expenses',
    'interests',
    "widget_tweaks",
    "items", 
    "visit_details",
    "reminders",   
    "quotes",
    "debug_toolbar",

]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
]


STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
ROOT_URLCONF = "oms_project.urls"


TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # This will now work, because BASE_DIR is a `Path`.
        "DIRS": [ BASE_DIR / "templates" ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


WSGI_APPLICATION = "oms_project.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'oms_solar_v2',      # updated name
        'USER': 'admin1',
        'PASSWORD': 'admin123',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]




# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"


USE_I18N = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_REDIRECT_URL = '/'      # where to go after a successful login
LOGOUT_REDIRECT_URL = '/accounts/login/'

LOGIN_URL = 'login'              # where @login_required sends you when not authenticated

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
}


ALLOWED_HOSTS = ["*"]     # during development, or set appropriately

# Allow the toolbar to appear when you access from localhost
INTERNAL_IPS = [
    "127.0.0.1",
    "localhost",
]