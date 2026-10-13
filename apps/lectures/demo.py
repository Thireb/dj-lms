"""Demo lectures for seed_demo (backlog LC3): one weekly schedule and two
single lectures for the first demo teacher. Past and live lectures come
with lecture states (roadmap 3.5); the services refuse a start in the past.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.academics.models import TeacherBatchSubject
from apps.core.tenancy import tenant_context
from apps.institutes.models import Institute
from apps.lectures.models import DeliveryMode, Lecture, RecurringSchedule
from apps.lectures.services import (
    LectureDetails,
    ScheduleDetails,
    create_lecture,
    create_schedule,
    generate_lectures,
)
from apps.people.demo import DEMO_TEACHER_EMAIL
from apps.people.models import TeacherProfile

DEMO_SCHEDULE_TITLE = "Weekly class"
DEMO_MEET_URL = "https://meet.example.com/demo-class"
MON_WED_FRI = [0, 2, 4]


def seed_lectures(institute: Institute) -> None:
    """Add the demo schedule and lectures once (a second run adds nothing)."""
    with tenant_context(institute):
        teacher = TeacherProfile.objects.filter(user__email=DEMO_TEACHER_EMAIL).first()
        if (
            teacher is None
            or RecurringSchedule.objects.filter(teacher=teacher).exists()
        ):
            return
        link = (
            TeacherBatchSubject.objects.filter(teacher=teacher)
            .select_related("batch", "subject")
            .order_by("batch__name", "subject__name")
            .first()
        )
        if link is None:
            return
        zone = ZoneInfo(institute.timezone)
        today = timezone.localtime(timezone.now(), zone).date()
        start = today + timedelta(days=1)
        schedule = create_schedule(
            institute,
            ScheduleDetails(
                title=f"{DEMO_SCHEDULE_TITLE}: {link.subject.name}",
                teacher=teacher,
                batch=link.batch,
                subjects=[link.subject],
                weekdays=MON_WED_FRI,
                start_time=time(16, 0),
                duration_minutes=60,
                start_date=start,
                end_date=start + timedelta(weeks=12),
                time_zone=institute.timezone,
                delivery_mode=DeliveryMode.MANUAL_LINK,
                meeting_url=DEMO_MEET_URL,
            ),
        )
        generate_lectures(schedule)
        for days, hour, title, mode in (
            (1, 11, f"{link.subject.name} revision", DeliveryMode.MANUAL_LINK),
            (3, 9, f"{link.subject.name} test", DeliveryMode.IN_PERSON),
        ):
            create_lecture(
                institute,
                LectureDetails(
                    title=title,
                    teacher=teacher,
                    batch=link.batch,
                    subjects=[link.subject],
                    starts_at=datetime.combine(
                        today + timedelta(days=days), time(hour), tzinfo=zone
                    ),
                    duration_minutes=60,
                    delivery_mode=mode,
                    meeting_url=DEMO_MEET_URL
                    if mode == DeliveryMode.MANUAL_LINK
                    else "",
                ),
            )


def reset_lectures(institute: Institute) -> int:
    """Delete the institute's lectures and schedules (before its teachers).

    Uses ``unscoped`` on purpose: a management command, one institute.
    """
    deleted = 0
    for model in (Lecture, RecurringSchedule):
        # unscoped: seed_demo --reset, limited to the demo institute.
        count, _ = model.unscoped.filter(institute=institute).delete()
        deleted += count
    return deleted
