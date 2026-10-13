"""Development settings."""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .db_url import database_config_from_url

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-dev-only-not-for-production",
)

_database_url = os.environ.get("DATABASE_URL")
if not _database_url:
    raise ImproperlyConfigured(
        "DATABASE_URL is required for development (see .env.example)."
    )

DATABASES = {"default": database_config_from_url(_database_url)}  # noqa: F405

# Tasks run inside the request unless a worker is running; set
# CELERY_ALWAYS_EAGER=false and start "celery -A config worker -B".
CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_ALWAYS_EAGER", "true").lower() in {
    "1",
    "true",
    "yes",
}
CELERY_TASK_EAGER_PROPAGATES = True
