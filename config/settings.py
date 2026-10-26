"""
Django settings for config project.
"""

import os
import sys
from pathlib import Path

from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-fallback-key-789234123')
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 't', 'yes')

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

LANGUAGE_CODE = 'en'
LANGUAGES = [
    ('en', _('English')),
    ('es', _('Spanish')),
]

TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_ROOT.mkdir(parents=True, exist_ok=True)
STATICFILES_DIRS = [BASE_DIR / 'inventory' / 'static']

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

IS_TESTING = 'test' in sys.argv or os.getenv('TESTING') == 'True'

if IS_TESTING:
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.InMemoryStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
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

# Gemini AI API Key
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

# Security & Hardening Settings
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

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

# Compilation & Build Metadata
APP_BUILD_TIME = os.getenv('APP_BUILD_TIME', '').strip()
APP_BUILD_COMMIT = os.getenv('APP_BUILD_COMMIT', '').strip()
APP_VERSION = os.getenv('APP_VERSION', '1.5.0').strip()
APP_ENV = os.getenv('APP_ENV', '').strip()


