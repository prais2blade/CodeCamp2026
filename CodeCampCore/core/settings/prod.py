from .base import *

DEBUG = False
_env_hosts = env.list('ALLOWED_HOSTS', default=[])
ALLOWED_HOSTS = list(set(_env_hosts + [
    'codecamp.com.ng',
    '.codecamp.com.ng',
    'www.codecamp.com.ng',
    'core.codecamp.com.ng',
    'portal.codecamp.com.ng',
    'attendance.codecamp.com.ng',
    '127.0.0.1',
    'localhost',
    '102.203.116.188',
]))

database_url = env("DATABASE_URL", default=None)

if database_url:
    DATABASES = {
        "default": env.db("DATABASE_URL"),
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': env('DB_NAME'),
            'USER': env('DB_USER'),
            'PASSWORD': env('DB_PASSWORD'),
            'HOST': env('DB_HOST'),
            'PORT': env('DB_PORT'),
        }
    }

MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

_env_csrf = env.list("CSRF_TRUSTED_ORIGINS", default=[])
CSRF_TRUSTED_ORIGINS = list(set(_env_csrf + [
    "https://codecamp.com.ng",
    "https://www.codecamp.com.ng",
    "https://core.codecamp.com.ng",
    "https://portal.codecamp.com.ng",
    "https://attendance.codecamp.com.ng",
    "http://codecamp.com.ng",
    "http://www.codecamp.com.ng",
    "http://core.codecamp.com.ng",
]))

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=True)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=True)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=True)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

WHITENOISE_MANIFEST_STRICT = False

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
