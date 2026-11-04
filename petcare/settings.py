"""
Django settings for PetBeacon project.
"""

from pathlib import Path
import os

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local development secrets; environment variables take precedence.
_local_env_file = BASE_DIR / '.env'
if _local_env_file.exists():
    for _line in _local_env_file.read_text(encoding='utf-8').splitlines():
        _line = _line.strip()
        if not _line or _line.startswith('#') or '=' not in _line:
            continue
        _name, _value = _line.split('=', 1)
        os.environ.setdefault(_name.strip(), _value.strip().strip('"').strip("'"))

# Security
# Generate a secret key with:
#   python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')

DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY environment variable must be set when DEBUG is False."
        )
    # Keep the fallback development-only; production requires an environment key.
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
    'admin_interface',
    'colorfield',
    'accounts.apps.AccountsConfig',
    'pets.apps.PetsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    # LocaleMiddleware depends on sessions and must run before URL resolution.
    'django.middleware.locale.LocaleMiddleware',
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
                'django.template.context_processors.i18n',
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

# Password validation
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

# Session and CSRF cookies
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 60 * 60 * 12
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_USE_SESSIONS = False

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# Security headers
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_SECURE_HSTS_SECONDS', 31536000))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    if os.environ.get('DJANGO_BEHIND_TLS_PROXY') == '1':
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Login throttling uses a process-local cache by default; configure a shared
# cache with DJANGO_CACHE_URL when running multiple workers.
if os.environ.get('DJANGO_CACHE_URL'):
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': os.environ['DJANGO_CACHE_URL'],
        }
    }

# File upload restrictions
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']
ALLOWED_DOCUMENT_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png', 'gif', 'doc', 'docx', 'txt']

LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 300

# Internationalization
# Bulgarian is the source catalog. Use the bundled commands to extract and
# compile translations on Windows without GNU gettext:
#   python manage.py i18n_extract && python manage.py i18n_compile
LANGUAGE_CODE = 'bg'
TIME_ZONE = 'Europe/Sofia'
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ('bg', 'Български'),
    ('en', 'English'),
]

LOCALE_PATHS = [BASE_DIR / 'locale']

# Static and media files
# Build the Tailwind bundle from static/css/input.css before collectstatic:
#   npm ci && npm run build && python manage.py collectstatic
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

if not DEBUG and not (BASE_DIR / 'static' / 'css' / 'app.css').exists():
    raise ImproperlyConfigured(
        "static/css/app.css is missing. Build it first: `npm ci && npm run build`."
    )

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Authentication redirects
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'pets:dashboard'
LOGOUT_REDIRECT_URL = 'pets:home'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
