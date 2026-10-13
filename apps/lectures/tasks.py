"""Background jobs for recurring schedules (roadmap 3.2, ARCHITECTURE 8)."""

from __future__ import annotations

from apps.core.tenancy import tenant_context
from apps.institutes.models import Institute
from apps.lectures.models import RecurringSchedule, ScheduleStatus
from apps.lectures.services import generate_lectures
from celery import shared_task


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
    """Nightly: move every active schedule forward to the new horizon."""
    created = 0
    for institute in Institute.objects.filter(is_active=True):
        with tenant_context(institute):
            active = RecurringSchedule.objects.filter(status=ScheduleStatus.ACTIVE)
            for schedule in active.select_related("teacher", "batch"):
                created += generate_lectures(schedule).created
    return created
