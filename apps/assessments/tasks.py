"""Background jobs for quizzes (roadmap 6.2, ARCHITECTURE 8)."""

from __future__ import annotations

import logging

from apps.assessments.services import remind_upcoming_quizzes
from apps.core.tenancy import tenant_context
from apps.institutes.models import Institute
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def remind_all_quizzes() -> int:
    """Every 5 minutes: "opens soon" for quizzes in the next hour (SPEC 7).
    One institute that fails is logged and skipped."""
    sent = 0
    for institute in Institute.objects.filter(is_active=True):
        with tenant_context(institute):
            try:
                sent += remind_upcoming_quizzes()
            except Exception:
                logger.exception("Quiz reminders: institute %s failed.", institute.pk)
    return sent
