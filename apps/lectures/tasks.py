"""Background jobs for recurring schedules (roadmap 3.2) and lecture states
(roadmap 3.5), ARCHITECTURE 8."""

from __future__ import annotations

import logging

from django.db import transaction

from apps.core.tenancy import tenant_context
from apps.institutes.models import Institute
from apps.lectures.models import RecurringSchedule, ScheduleStatus
from apps.lectures.services import finish_ended_lectures, generate_lectures
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def generate_schedule_lectures(institute_id: int, schedule_id: int) -> int:
    """After a save: make the schedule's lectures up to the horizon."""
    institute = Institute.objects.filter(pk=institute_id, is_active=True).first()
    if institute is None:
        return 0
    with tenant_context(institute):
        schedule = RecurringSchedule.objects.filter(pk=schedule_id).first()
        if schedule is None:
            return 0
        return generate_lectures(schedule).created


@shared_task
def extend_all_schedules() -> int:
    """Nightly: move every active schedule forward to the new horizon. One
    schedule that fails is logged and skipped; the others still run
    (external audit L1). Each schedule runs in its own transaction."""
    created = 0
    for institute in Institute.objects.filter(is_active=True):
        with tenant_context(institute):
            active = RecurringSchedule.objects.filter(status=ScheduleStatus.ACTIVE)
            for schedule in active.select_related("teacher", "batch"):
                try:
                    created += generate_lectures(schedule).created
                except Exception:
                    logger.exception(
                        "Nightly run: schedule %s (institute %s) failed.",
                        schedule.pk,
                        institute.pk,
                    )
    return created


@shared_task
def finish_all_ended_lectures() -> int:
    """Every 5 minutes: lectures past their end close (finished or not
    held). An inactive institute catches up after it is active again. One
    institute that fails is logged and skipped (external audit L1)."""
    closed = 0
    for institute in Institute.objects.filter(is_active=True):
        with tenant_context(institute):
            try:
                with transaction.atomic():
                    closed += finish_ended_lectures(institute)
            except Exception:
                logger.exception("Finish run: institute %s failed.", institute.pk)
    return closed
