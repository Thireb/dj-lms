"""Shared Django settings."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = "django-insecure-change-me"

DEBUG = False

ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "crispy_forms",
    "apps.academics",
    "apps.accounts",
    "apps.core",
    "apps.institutes",
    "apps.people",
    "apps.superadmin",
    "apps.ui",
]

AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "accounts:login"
LOGOUT_REDIRECT_URL = "accounts:login"

# Without "remember me" the cookie ends at browser close and the server
# session after 12 hours; "remember me" keeps it for 14 days (audit L2).
SESSION_COOKIE_AGE = 60 * 60 * 12
REMEMBER_ME_SECONDS = 60 * 60 * 24 * 14

# Client IP for sign-in limits: a header your proxy always sets, for example
# HTTP_X_REAL_IP. Empty means REMOTE_ADDR (no proxy).
TRUSTED_PROXY_IP_HEADER = os.environ.get("TRUSTED_PROXY_IP_HEADER", "")
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

CRISPY_ALLOWED_TEMPLATE_PACKS = ("ui/forms",)
CRISPY_TEMPLATE_PACK = "ui/forms"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.django_admin.DjangoAdminGateMiddleware",
    "apps.core.middleware.tenant.TenantMiddleware",
    "apps.core.middleware.timezone.TimezoneMiddleware",
    "apps.people.middleware.StudentPortalAccessMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = ""
EMAIL_HOST = ""
EMAIL_PORT = 587
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = ""

STORAGE_BUCKET = ""
STORAGE_ACCESS_KEY = ""
STORAGE_SECRET_KEY = ""
STORAGE_ENDPOINT = ""

SENTRY_DSN = ""
