"""Celery app (background jobs, ARCHITECTURE section 8).

Run a worker with the nightly jobs: ``celery -A config worker -B -l info``.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("lms")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
