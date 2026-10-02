"""
Django settings for PetCare project.
"""

from pathlib import Path
import os

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------
# SECURITY — Secret Key
# Generate one with:
#   python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
# --------------------------------------------------------------------------
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')

DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY environment variable must be set when DEBUG is False."
        )
    # Development only: an ephemeral key means sessions are invalidated on every
    # restart, which is preferable to shipping a hard-coded key to production.
    SECRET_KEY = 'django-insecure-dev-only-key-do-not-use-in-production-0000'

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

if not DEBUG and ALLOWED_HOSTS == ['']:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set when DEBUG is False.")

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Local apps
    'accounts.apps.AccountsConfig',
    'pets.apps.PetsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'petcare.urls'

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
                'pets.context_processors.petcare_badges',
            ],
        },
    },
]

WSGI_APPLICATION = 'petcare.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# --------------------------------------------------------------------------
# SECURITY — Password Validation (strong rules)
# --------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# --------------------------------------------------------------------------
# SECURITY — Session & Cookie hardening
# --------------------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True          # JS cannot read the session cookie
SESSION_COOKIE_SAMESITE = 'Lax'        # Blocks cross-site request forgery
SESSION_COOKIE_AGE = 60 * 60 * 12      # 12-hour session lifetime
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

CSRF_COOKIE_HTTPONLY = False            # Must be False so JS AJAX can read it
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_USE_SESSIONS = False              # Keep default cookie-based CSRF

# Only ever transmitted over HTTPS (automatically enabled when DEBUG is False).
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# --------------------------------------------------------------------------
# SECURITY — HTTP Headers
# --------------------------------------------------------------------------
X_FRAME_OPTIONS = 'DENY'                # Blocks all clickjacking
SECURE_CONTENT_TYPE_NOSNIFF = True     # X-Content-Type-Options: nosniff
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_SECURE_HSTS_SECONDS', 31536000))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    if os.environ.get('DJANGO_BEHIND_TLS_PROXY') == '1':
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# --------------------------------------------------------------------------
# CACHES
#
# Used by the login rate limiter. The default local-memory backend is per
# process; switch to Redis/Memcached (e.g. via DJANGO_CACHE_URL) before running
# multiple workers or containers, otherwise the lockout counters are not shared.
# --------------------------------------------------------------------------
if os.environ.get('DJANGO_CACHE_URL'):
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': os.environ['DJANGO_CACHE_URL'],
        }
    }

# --------------------------------------------------------------------------
# SECURITY — File upload restrictions
# --------------------------------------------------------------------------
# Max upload size: 5 MB (enforced in forms)
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']
ALLOWED_DOCUMENT_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png', 'gif', 'doc', 'docx', 'txt']

# --------------------------------------------------------------------------
# SECURITY — Login attempt throttling (simple cooloff via session)
# --------------------------------------------------------------------------
LOGIN_MAX_ATTEMPTS = 5              # After this many failures, lock for LOCKOUT seconds
LOGIN_LOCKOUT_SECONDS = 300         # 5 minutes

# --------------------------------------------------------------------------
# Internationalization
# --------------------------------------------------------------------------
LANGUAGE_CODE = 'bg'
TIME_ZONE = 'Europe/Sofia'
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Static & Media files
# --------------------------------------------------------------------------
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# --------------------------------------------------------------------------
# Authentication redirects
# --------------------------------------------------------------------------
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'pets:dashboard'
LOGOUT_REDIRECT_URL = 'pets:home'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
