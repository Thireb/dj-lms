"""Production settings."""

import os
from urllib.parse import unquote, urlparse

from .base import *  # noqa: F403

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

_database_url = os.environ["DATABASE_URL"]
_parsed = urlparse(_database_url)
DATABASES = {  # noqa: F405
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _parsed.path.lstrip("/"),
        "USER": unquote(_parsed.username or ""),
        "PASSWORD": unquote(_parsed.password or ""),
        "HOST": _parsed.hostname or "",
        "PORT": str(_parsed.port or ""),
    }
}

REDIS_URL = os.environ.get("REDIS_URL", "")
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
