"""Shared Django settings."""

import os
from pathlib import Path

from celery.schedules import crontab

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
    "apps.assessments",
    "apps.attendance",
    "apps.accounts",
    "apps.core",
    "apps.institutes",
    "apps.finance",
    "apps.lectures",
    "apps.messaging",
    "apps.notifications",
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

# Private uploads (guardian fee receipts, roadmap 7.3b; owner decision
# 2026-10-16): outside static and never served directly; a view that checks
# the user's access streams each file. Use a persistent volume in production.
PRIVATE_MEDIA_ROOT = Path(
    os.environ.get("PRIVATE_MEDIA_ROOT") or BASE_DIR / "private_media"
)
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

# Celery (background jobs). Redis is the broker; no result backend is used.
CELERY_BROKER_URL = os.environ.get("REDIS_URL") or "redis://localhost:6379/0"
CELERY_TASK_IGNORE_RESULT = True
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULE = {
    # Adds the next days of every active recurring schedule (roadmap 3.2).
    "extend-lecture-schedules": {
        "task": "apps.lectures.tasks.extend_all_schedules",
        "schedule": crontab(hour=0, minute=30),
    },
    # Lectures past their end become finished (roadmap 3.5, SPEC 6.4).
    "finish-ended-lectures": {
        "task": "apps.lectures.tasks.finish_all_ended_lectures",
        "schedule": crontab(minute="*/5"),
    },
    # "Starts in 15 minutes" for lectures (roadmap 6.2, SPEC 7).
    "remind-lectures": {
        "task": "apps.lectures.tasks.remind_all_lectures",
        "schedule": crontab(minute="*/5"),
    },
    # "Quiz opens soon", 1 hour before (roadmap 6.2, SPEC 7).
    "remind-quizzes": {
        "task": "apps.assessments.tasks.remind_all_quizzes",
        "schedule": crontab(minute="*/5"),
    },
    # Fee reminders and the late fee, by each institute's date (roadmap 7.4).
    "remind-challans": {
        "task": "apps.finance.tasks.remind_all_challans",
        "schedule": crontab(minute=15),
    },
    # Notifications older than 90 days are deleted (roadmap 6.1, SPEC 7).
    "delete-old-notifications": {
        "task": "apps.notifications.tasks.delete_all_old_notifications",
        "schedule": crontab(hour=1, minute=0),
    },
}
