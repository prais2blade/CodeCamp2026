import os
from pathlib import Path
import environ

# Load env
env = environ.Env()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env("SECRET_KEY")

# Competition feature toggles
COMPETITION_ACTIVE = True  # set False to show "competition closed" page
COMPETITION_REGISTRATION_OPEN = True  # set False to close registration
COMPETITION_GLOBAL_ACTIVE = True

# Optional: default active year (fallback if none marked active in DB)
COMPETITION_DEFAULT_YEAR = 2026
# ISO string used for countdown (frontend)
COMPETITION_START_ISO = "2026-02-28T09:00:00"  # adjust to real date/time


# --------------------------------------
# BASE SETTINGS (shared across all modes)
# --------------------------------------

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'adminlte3',
    'adminlte3_theme',

    # Multi-tenant and core apps
    'apps.tenants',
    'apps.accounts',
    'apps.staff',
    'apps.dashboard',
    'apps.courses',
    'apps.payments',
    'apps.scheduling',
    'apps.mailing',
    'apps.notifications',
    'apps.website',
    'apps.blog',
    'apps.competition',
    'apps.tasks',
]

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.tenants.middleware.TenantMiddleware',
    'apps.accounts.middleware.OnboardingMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

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
                'apps.competition.context_processors.current_edition',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
]

EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")

ATTENDANCE_API_KEY = env("ATTENDANCE_API_KEY", default="")
CORE_API_KEY = env("CORE_API_KEY", default="")
REGISTRATION_API_KEY = env("REGISTRATION_API_KEY", default="")
ATTENDANCE_API_URL = env("ATTENDANCE_API_URL", default="")
REGISTRATION_API_URL = env("REGISTRATION_API_URL", default="")

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lagos'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'
LOGOUT_REDIRECT_URL = 'login'
