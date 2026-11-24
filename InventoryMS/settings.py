import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Explicit environment overrides .env; alternate files support isolated checks.
load_dotenv(os.environ.get('DJANGO_ENV_FILE', BASE_DIR / '.env'), override=False)


def env_bool(name, default=False):
    value = os.environ.get(name, str(default)).strip().lower()
    if value in ('1', 'true', 'yes', 'on'):
        return True
    if value in ('0', 'false', 'no', 'off'):
        return False
    raise ImproperlyConfigured(f'{name} must be true or false.')


def env_list(name, default=''):
    return [part.strip() for part in os.environ.get(name, default).split(',') if part.strip()]


DEBUG = env_bool('DEBUG', False)
SECRET_KEY = os.environ.get('SECRET_KEY', '')
if not SECRET_KEY:
    raise ImproperlyConfigured('SECRET_KEY is required; generate a key and store it in .env.')
if not DEBUG and (len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith('django-insecure-')):
    raise ImproperlyConfigured('SECRET_KEY must contain at least 50 characters and 5 distinct characters when DEBUG=False, without the django-insecure- prefix.')

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]')
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')
DJANGO_SECURE_SSL = env_bool('DJANGO_SECURE_SSL', False)
SECURE_SSL_REDIRECT = DJANGO_SECURE_SSL
SESSION_COOKIE_SECURE = DJANGO_SECURE_SSL
CSRF_COOKIE_SECURE = DJANGO_SECURE_SSL
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if DJANGO_SECURE_SSL else None
try:
    SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '3600')) if DJANGO_SECURE_SSL else 0
except ValueError as error:
    raise ImproperlyConfigured('SECURE_HSTS_SECONDS must be a nonnegative integer.') from error
if SECURE_HSTS_SECONDS < 0:
    raise ImproperlyConfigured('SECURE_HSTS_SECONDS must be a nonnegative integer.')
SECURE_HSTS_INCLUDE_SUBDOMAINS = DJANGO_SECURE_SSL and env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD = DJANGO_SECURE_SSL and env_bool('SECURE_HSTS_PRELOAD', False)

# Tests must work on a fresh checkout, without generated staticfiles/manifest.
# Explicit production-storage tests override this alias locally.
TESTING = sys.argv[1:2] == ['test']

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'phonenumber_field',
    'crispy_forms',
    'crispy_bootstrap5',
    'imagekit',
    'django_extensions',
    'django_filters',
    'django_tables2',

    'store.apps.StoreConfig',
    'accounts.apps.AccountsConfig',
    'transactions.apps.TransactionsConfig',
    'invoice.apps.InvoiceConfig',
    'bills.apps.BillsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'InventoryMS.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'InventoryMS.wsgi.application'


# Generic DB_* variables take precedence over legacy Azure variables, even if blank.
def db_value(name, legacy=None, default=''):
    if name in os.environ:
        return os.environ[name]
    return os.environ.get(legacy, default) if legacy else default


DB_HOST = db_value('DB_HOST', 'AZURE_POSTGRESQL_HOST')
DB_ENGINE = os.environ.get('DB_ENGINE', 'postgresql' if DB_HOST else 'sqlite').strip().lower()
if DB_ENGINE in ('postgres', 'postgresql', 'django.db.backends.postgresql'):
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': db_value('DB_NAME', 'AZURE_POSTGRESQL_DATABASE'),
        'USER': db_value('DB_USER', 'AZURE_POSTGRESQL_USERNAME'),
        'PASSWORD': db_value('DB_PASSWORD', 'AZURE_POSTGRESQL_PASSWORD'),
        'HOST': DB_HOST,
        'PORT': db_value('DB_PORT', 'AZURE_POSTGRESQL_PORT', '5432'),
    }}
    if not all(DATABASES['default'][key] for key in ('NAME', 'USER', 'HOST')):
        raise ImproperlyConfigured('PostgreSQL requires DB_NAME, DB_USER and DB_HOST (or legacy Azure equivalents).')
elif DB_ENGINE in ('sqlite', 'sqlite3', 'django.db.backends.sqlite3'):
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('DB_NAME', BASE_DIR / 'db.sqlite3'),
    }}
else:
    raise ImproperlyConfigured('DB_ENGINE must be sqlite or postgresql.')


# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

LOGIN_URL = 'user-login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_URL = 'logout'

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

#STATIC_URL = 'static/'
#STATICFILES_DIRS = [os.path.join(BASE_DIR,'static')
#]
#STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
#MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', BASE_DIR / 'media'))
#MEDIA_URL = '/images/'

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

#DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

#CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
#CRISPY_TEMPLATE_PACK = "bootstrap5"


#SCM_DO_BUILD_DURING_DEPLOYMENT = True

#SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

STATIC_URL = 'static/'


STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')


STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]


MEDIA_URL = '/images/'
MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', BASE_DIR / 'media'))


STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': ('django.contrib.staticfiles.storage.StaticFilesStorage' if TESTING
                    else 'whitenoise.storage.CompressedManifestStaticFilesStorage'),
    },
}


CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"
