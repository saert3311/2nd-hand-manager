"""
Django settings for config project.
"""

import os
import secrets
import sys
from collections.abc import Mapping
from pathlib import Path

from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env
load_dotenv(BASE_DIR / '.env')


def resolve_security_settings(
    debug: bool,
    is_testing: bool,
    env: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """
    Resolve secret key and transport/cookie security defaults.
    Enforces fail-closed production defaults outside DEBUG and test runs.
    """
    source = os.environ if env is None else env
    raw_secret = (source.get('SECRET_KEY') or '').strip()
    is_prod_runtime = not debug and not is_testing

    if is_prod_runtime:
        if not raw_secret or raw_secret.startswith('django-insecure-'):
            secret_key = secrets.token_urlsafe(50)
        else:
            secret_key = raw_secret
        try:
            hsts_seconds = int(source.get('SECURE_HSTS_SECONDS', '31536000') or '31536000')
        except (TypeError, ValueError):
            hsts_seconds = 31536000
        return {
            'SECRET_KEY': secret_key,
            'SESSION_COOKIE_SECURE': source.get('SESSION_COOKIE_SECURE', 'True').lower() in ('true', '1', 'yes'),
            'CSRF_COOKIE_SECURE': source.get('CSRF_COOKIE_SECURE', 'True').lower() in ('true', '1', 'yes'),
            'SECURE_HSTS_SECONDS': hsts_seconds,
            'SECURE_HSTS_INCLUDE_SUBDOMAINS': (
                source.get('SECURE_HSTS_INCLUDE_SUBDOMAINS', 'True').lower() in ('true', '1', 'yes')
            ),
            'SECURE_HSTS_PRELOAD': source.get('SECURE_HSTS_PRELOAD', 'True').lower() in ('true', '1', 'yes'),
            'SECURE_SSL_REDIRECT': source.get('SECURE_SSL_REDIRECT', 'False').lower() in ('true', '1', 'yes'),
            'SECURE_REFERRER_POLICY': 'strict-origin-when-cross-origin',
            'SECURE_CROSS_ORIGIN_OPENER_POLICY': 'same-origin',
        }

    return {
        'SECRET_KEY': raw_secret or 'django-insecure-dev-fallback-key-789234123',
        'SESSION_COOKIE_SECURE': False,
        'CSRF_COOKIE_SECURE': False,
        'SECURE_HSTS_SECONDS': 0,
        'SECURE_HSTS_INCLUDE_SUBDOMAINS': False,
        'SECURE_HSTS_PRELOAD': False,
        'SECURE_SSL_REDIRECT': False,
        'SECURE_REFERRER_POLICY': 'strict-origin-when-cross-origin',
        'SECURE_CROSS_ORIGIN_OPENER_POLICY': 'same-origin',
    }


IS_TESTING = 'test' in sys.argv or os.getenv('TESTING') == 'True'
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 't', 'yes')
_SECURITY_DEFAULTS = resolve_security_settings(DEBUG, IS_TESTING, os.environ)
SECRET_KEY = _SECURITY_DEFAULTS['SECRET_KEY']

allowed_hosts_env = os.getenv('ALLOWED_HOSTS', '*')
ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_env.split(',') if h.strip()]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'storages',
    'inventory.apps.InventoryConfig',
    'storefront.apps.StorefrontConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'inventory.middleware.CurrentUserMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'inventory' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.i18n',
                'inventory.context_processors.notifications',
                'inventory.context_processors.turnstile',
                'inventory.context_processors.pwa_push',
                'inventory.context_processors.build_info',
                'storefront.context_processors.storefront_config',
            ],
        },
    },
]


WSGI_APPLICATION = 'config.wsgi.application'

DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
if DATABASE_URL:
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    }
else:
    data_dir = BASE_DIR / 'data'
    db_path = data_dir / 'db.sqlite3' if data_dir.exists() else BASE_DIR / 'db.sqlite3'
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': db_path,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = os.getenv('LANGUAGE_CODE', 'en' if IS_TESTING else 'es')
LANGUAGES = [
    ('es', _('Spanish')),
    ('en', _('English')),
]

TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# Static files (CSS, JavaScript, Images) — AppDirectoriesFinder collects inventory/static & storefront/static
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_ROOT.mkdir(parents=True, exist_ok=True)
STATICFILES_DIRS = []

# Media files (User uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Oracle Cloud Infrastructure (OCI) Object Storage Settings
OCI_STORAGE_BUCKET_NAME = os.getenv('OCI_STORAGE_BUCKET_NAME', '').strip()
OCI_STORAGE_ACCESS_KEY = os.getenv('OCI_STORAGE_ACCESS_KEY', '').strip()
OCI_STORAGE_SECRET_KEY = os.getenv('OCI_STORAGE_SECRET_KEY', '').strip()
OCI_STORAGE_NAMESPACE = os.getenv('OCI_STORAGE_NAMESPACE', '').strip()
OCI_STORAGE_REGION = os.getenv('OCI_STORAGE_REGION', '').strip()
OCI_STORAGE_ENDPOINT_URL = os.getenv('OCI_STORAGE_ENDPOINT_URL', '').strip()

if not OCI_STORAGE_ENDPOINT_URL and OCI_STORAGE_NAMESPACE and OCI_STORAGE_REGION:
    OCI_STORAGE_ENDPOINT_URL = (
        f"https://{OCI_STORAGE_NAMESPACE}.compat.objectstorage.{OCI_STORAGE_REGION}.oraclecloud.com"
    )

if IS_TESTING:
    PASSWORD_HASHERS = [
        'django.contrib.auth.hashers.MD5PasswordHasher',
    ]
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.InMemoryStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'test_console_errors': {
                'level': 'ERROR',
                'class': 'logging.StreamHandler',
            },
        },
        'loggers': {
            'django.request': {
                'handlers': ['test_console_errors'],
                'level': 'ERROR',
                'propagate': False,
            },
        },
    }
elif OCI_STORAGE_BUCKET_NAME and OCI_STORAGE_ACCESS_KEY and OCI_STORAGE_SECRET_KEY:
    STORAGES = {
        'default': {
            'BACKEND': 'inventory.services.storage.OCIObjectStorage',
            'OPTIONS': {
                'access_key': OCI_STORAGE_ACCESS_KEY,
                'secret_key': OCI_STORAGE_SECRET_KEY,
                'bucket_name': OCI_STORAGE_BUCKET_NAME,
                'endpoint_url': OCI_STORAGE_ENDPOINT_URL or None,
                'region_name': OCI_STORAGE_REGION or None,
            },
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
        },
    }
else:
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
        },
    }

# Authentication redirects
LOGIN_URL = 'inventory:login'
LOGIN_REDIRECT_URL = 'inventory:dashboard'
LOGOUT_REDIRECT_URL = 'inventory:login'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Gemini AI API Key & API Version (v1beta required for -latest aliases and JSON mode)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_API_VERSION = os.getenv('GEMINI_API_VERSION', 'v1beta').strip() or 'v1beta'

# Security & Hardening Settings
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = _SECURITY_DEFAULTS['SESSION_COOKIE_SECURE']
CSRF_COOKIE_SECURE = _SECURITY_DEFAULTS['CSRF_COOKIE_SECURE']
SECURE_HSTS_SECONDS = _SECURITY_DEFAULTS['SECURE_HSTS_SECONDS']
SECURE_HSTS_INCLUDE_SUBDOMAINS = _SECURITY_DEFAULTS['SECURE_HSTS_INCLUDE_SUBDOMAINS']
SECURE_HSTS_PRELOAD = _SECURITY_DEFAULTS['SECURE_HSTS_PRELOAD']
SECURE_SSL_REDIRECT = _SECURITY_DEFAULTS['SECURE_SSL_REDIRECT']
SECURE_REFERRER_POLICY = _SECURITY_DEFAULTS['SECURE_REFERRER_POLICY']
SECURE_CROSS_ORIGIN_OPENER_POLICY = _SECURITY_DEFAULTS['SECURE_CROSS_ORIGIN_OPENER_POLICY']

# Cache-backed Rate Limiting Defaults
LOGIN_RATE_LIMIT_ATTEMPTS = int(os.getenv('LOGIN_RATE_LIMIT_ATTEMPTS', '10'))
LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv('LOGIN_RATE_LIMIT_WINDOW_SECONDS', '300'))
AI_RATE_LIMIT_REQUESTS = int(os.getenv('AI_RATE_LIMIT_REQUESTS', '20'))
AI_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv('AI_RATE_LIMIT_WINDOW_SECONDS', '60'))

# Reverse Proxy / Cloudflare Tunnel Support
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
csrf_origins_env = os.getenv('CSRF_TRUSTED_ORIGINS', '')
if csrf_origins_env:
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_origins_env.split(',') if origin.strip()]

# Cloudflare Turnstile Bot Protection
TURNSTILE_SITE_KEY = os.getenv('TURNSTILE_SITE_KEY', '')
TURNSTILE_SECRET_KEY = os.getenv('TURNSTILE_SECRET_KEY', '')
TURNSTILE_ENABLED = (
    os.getenv('TURNSTILE_ENABLED', 'False').lower() in ('true', '1', 'yes')
    and bool(TURNSTILE_SITE_KEY and TURNSTILE_SECRET_KEY)
)
TURNSTILE_TIMEOUT = float(os.getenv('TURNSTILE_TIMEOUT', '5.0'))

# SQLite Automated Database Backup Settings
DB_BACKUP_RETENTION_DAYS = int(os.getenv('DB_BACKUP_RETENTION_DAYS', '30'))
DB_BACKUP_PREFIX = os.getenv('DB_BACKUP_PREFIX', 'backups/db/').strip()
if DB_BACKUP_PREFIX and not DB_BACKUP_PREFIX.endswith('/'):
    DB_BACKUP_PREFIX += '/'

# Web Push Notifications (VAPID) & Live Signal Settings
VAPID_PUBLIC_KEY = os.getenv('VAPID_PUBLIC_KEY', '').strip()
VAPID_PRIVATE_KEY = os.getenv('VAPID_PRIVATE_KEY', '').strip()
VAPID_CLAIMS_EMAIL = os.getenv('VAPID_CLAIMS_EMAIL', 'mailto:admin@localhost').strip()
if VAPID_CLAIMS_EMAIL and not VAPID_CLAIMS_EMAIL.startswith('mailto:'):
    VAPID_CLAIMS_EMAIL = f'mailto:{VAPID_CLAIMS_EMAIL}'

PUSH_NOTIFICATIONS_LIVE_SIGNALS = (
    os.getenv('PUSH_NOTIFICATIONS_LIVE_SIGNALS', 'False').lower() in ('true', '1', 't', 'yes')
)

# Intake Sourcing Batch Notification Inactivity Debounce (Minutes)
try:
    INTAKE_SESSION_DEBOUNCE_MINUTES = int(os.getenv('INTAKE_SESSION_DEBOUNCE_MINUTES', '15'))
except (TypeError, ValueError):
    INTAKE_SESSION_DEBOUNCE_MINUTES = 15

# Soft-deleted trash retention window in days before automated purging
try:
    TRASH_RETENTION_DAYS = int(os.getenv('TRASH_RETENTION_DAYS', '30'))
except (TypeError, ValueError):
    TRASH_RETENTION_DAYS = 30

# Compilation & Build Metadata
APP_BUILD_TIME = os.getenv('APP_BUILD_TIME', '').strip()
APP_BUILD_COMMIT = os.getenv('APP_BUILD_COMMIT', '').strip()
APP_VERSION = os.getenv('APP_VERSION', '2.11.0').strip()
APP_ENV = os.getenv('APP_ENV', '').strip()

# Google Tag Manager Container ID (shared across rapidopackvalencia.es and store subdomain)
GTM_CONTAINER_ID = os.getenv('GTM_CONTAINER_ID', 'GTM-PGBXBVXJ').strip()


