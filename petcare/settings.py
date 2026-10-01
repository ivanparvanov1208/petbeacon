"""
Django settings for PetCare project.
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------
# SECURITY — Secret Key
# In production: set the environment variable DJANGO_SECRET_KEY
# --------------------------------------------------------------------------
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-change-this-before-deploying-to-production-!!!!'
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

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

# In production with HTTPS, uncomment these:
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True

# --------------------------------------------------------------------------
# SECURITY — HTTP Headers
# --------------------------------------------------------------------------
X_FRAME_OPTIONS = 'SAMEORIGIN'        # Prevents clickjacking (allow same-origin for admin)
SECURE_CONTENT_TYPE_NOSNIFF = True    # X-Content-Type-Options: nosniff
SECURE_BROWSER_XSS_FILTER = True      # Legacy X-XSS-Protection header

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
