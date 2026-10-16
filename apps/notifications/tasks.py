"""Background jobs for notifications (roadmap 6.1, ARCHITECTURE 8)."""

from __future__ import annotations

import logging

from apps.core.tenancy import tenant_context
from apps.institutes.models import Institute
from apps.notifications.services import delete_old
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def delete_all_old_notifications() -> int:
    """Nightly: delete notifications older than 90 days in every institute,
    active or not. One institute that fails is logged and skipped."""
    deleted = 0
    for institute in Institute.objects.all():
        with tenant_context(institute):
            try:
                deleted += delete_old()
            except Exception:
                logger.exception(
                    "Old notifications: institute %s failed.", institute.pk
                )
    return deleted
