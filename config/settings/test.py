"""Test settings (pytest and CI)."""

import os

from .base import *  # noqa: F403
from .db_url import database_config_from_url

DEBUG = False

SECRET_KEY = "test-secret-key-not-for-production"

INSTALLED_APPS = [*INSTALLED_APPS, "tests.testapp"]  # noqa: F405

_default_test_database_url = "postgres://lms:lms_dev_password@localhost:5432/lms_test"
_database_url = os.environ.get("DATABASE_URL", _default_test_database_url)

_db = database_config_from_url(_database_url)
# The mutation check gives each parallel worker its own test database.
_db["TEST"] = {"NAME": os.environ.get("TEST_DB_NAME", "lms_test")}
DATABASES = {"default": _db}  # noqa: F405

PASSWORD_HASHERS = [  # noqa: F405
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

ROOT_URLCONF = "config.urls_test"  # noqa: F405

_MIDDLEWARE = list(MIDDLEWARE)  # noqa: F405  # from star import
MIDDLEWARE = [
    *_MIDDLEWARE,
    "tests.accounts.middleware.SubAdminTestMenuMiddleware",
]
