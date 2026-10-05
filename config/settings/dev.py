"""Development settings."""

import os
from urllib.parse import unquote, urlparse

from .base import *  # noqa: F403

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-dev-only-not-for-production",
)

_database_url = os.environ.get("DATABASE_URL")
if _database_url:
    parsed = urlparse(_database_url)
    DATABASES = {  # noqa: F405
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or ""),
        }
    }
else:
    DATABASES = {  # noqa: F405
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
        }
    }
