"""Background jobs for fees (roadmap Phase 7, ARCHITECTURE 8)."""

from __future__ import annotations

import logging
from datetime import date

from kombu.exceptions import OperationalError as KombuOperationalError

from apps.core.tenancy import tenant_context
from apps.finance.services import generate_challans
from apps.institutes.models import Institute
from apps.people.models import StudentProfile
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def generate_challans_task(
    institute_id: int, month: str, due_date: str, student_ids: list[int]
) -> int:
    """Bulk challan generation (roadmap 7.2). Ids and ISO dates only."""
    institute = Institute.objects.filter(pk=institute_id, is_active=True).first()
    if institute is None:
        return 0
    with tenant_context(institute):
        students = list(StudentProfile.objects.filter(pk__in=student_ids))
        made = generate_challans(
            institute,
            date.fromisoformat(month),
            date.fromisoformat(due_date),
            students,
        )
    return len(made)


def queue_challans(
    institute: Institute, month: date, due_date: date, ids: list[int]
) -> None:
    """Queue the task; when the broker is down, make the challans here (the
    same fallback as the lecture generator, external audit X1)."""
    args = (institute.pk, month.isoformat(), due_date.isoformat(), ids)
    try:
        generate_challans_task.delay(*args)
        return
    except KombuOperationalError:
        logger.warning("Broker unavailable; making %s challans now.", len(ids))
    generate_challans_task(*args)
