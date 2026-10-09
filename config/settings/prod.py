"""Production settings."""

import os

from .base import *  # noqa: F403
from .db_url import database_config_from_url

DEBUG = False

SECRET_KEY = os.environ["SECRET_KEY"]

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

_csrf_origins = os.environ.get("CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in _csrf_origins.split(",") if origin.strip()
]

DATABASES = {  # noqa: F405
    "default": database_config_from_url(os.environ["DATABASE_URL"]),
}

REDIS_URL = os.environ.get("REDIS_URL", "")
# Sign-in limits need one cache shared by every worker (audit H1). Django's
# Redis backend needs the "redis" package, added with deployment (Phase 12).
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() in {
    "1",
    "true",
    "yes",
}
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "")

STORAGE_BUCKET = os.environ.get("STORAGE_BUCKET", "")
STORAGE_ACCESS_KEY = os.environ.get("STORAGE_ACCESS_KEY", "")
STORAGE_SECRET_KEY = os.environ.get("STORAGE_SECRET_KEY", "")
STORAGE_ENDPOINT = os.environ.get("STORAGE_ENDPOINT", "")

SENTRY_DSN = os.environ.get("SENTRY_DSN", "")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "true").lower() in {
    "1",
    "true",
    "yes",
}
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
