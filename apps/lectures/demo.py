"""Demo lectures for seed_demo (backlog LC3 and LC5): one weekly schedule,
two single lectures, three finished lectures from last week and one live
lecture for the first demo teacher.

The services refuse a start in the past, so the past and live lectures are
saved directly (still inside the tenant context).
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.academics.models import StudentBatchSubject, TeacherBatchSubject
from apps.core.tenancy import tenant_context
from apps.institutes.models import Institute
from apps.lectures.models import (
    DeliveryMode,
    Lecture,
    LectureStatus,
    RecurringSchedule,
)
from apps.lectures.services import (
    LectureDetails,
    ScheduleDetails,
    create_lecture,
    create_schedule,
    generate_lectures,
)
from apps.people.demo import DEMO_STUDENT_EMAIL, DEMO_TEACHER_EMAIL
from apps.people.models import TeacherProfile

DEMO_SCHEDULE_TITLE = "Weekly class"
DEMO_MEET_URL = "https://meet.example.com/demo-class"
MON_WED_FRI = [0, 2, 4]


def _shared_link(teacher: TeacherProfile) -> TeacherBatchSubject | None:
    """The teacher's batch and subject that the demo student also takes, so
    the student and guardian demo show lectures and Join (Phase 3 audit P3-3).
    Any of the teacher's pairs when they share none."""
    links = (
        TeacherBatchSubject.objects.filter(teacher=teacher)
        .select_related("batch", "subject")
        .order_by("batch__name", "subject__name")
    )
    studied = StudentBatchSubject.objects.filter(
        student__user__email=DEMO_STUDENT_EMAIL
    ).values_list("batch_id", "subject_id")
    shared = set(studied)
    for link in links:
        if (link.batch_id, link.subject_id) in shared:
            return link
    return links.first()


def seed_lectures(institute: Institute) -> None:
    """Add the demo schedule and lectures once (a second run adds nothing)."""
    with tenant_context(institute):
        teacher = TeacherProfile.objects.filter(user__email=DEMO_TEACHER_EMAIL).first()
        if (
            teacher is None
            or RecurringSchedule.objects.filter(teacher=teacher).exists()
        ):
            return
        link = _shared_link(teacher)
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
        _seed_past_and_live(institute, teacher, link)


def _seed_past_and_live(institute: Institute, teacher, link) -> None:
    now = timezone.now().replace(second=0, microsecond=0)
    name = link.subject.name
    lectures = [
        (f"{name} basics 1", now - timedelta(days=7), LectureStatus.FINISHED),
        (f"{name} basics 2", now - timedelta(days=5), LectureStatus.FINISHED),
        (f"{name} basics 3", now - timedelta(days=2), LectureStatus.FINISHED),
        # Started 10 minutes ago, so the demo shows a live class and Join.
        (f"{name} live class", now - timedelta(minutes=10), LectureStatus.LIVE),
    ]
    for title, starts_at, status in lectures:
        lecture = Lecture.objects.create(
            institute=institute,
            title=title,
            teacher=teacher,
            batch=link.batch,
            starts_at=starts_at,
            duration_minutes=60,
            status=status,
            delivery_mode=DeliveryMode.MANUAL_LINK,
            meeting_url=DEMO_MEET_URL,
            started_at=starts_at,
            ended_at=starts_at + timedelta(minutes=55)
            if status == LectureStatus.FINISHED
            else None,
        )
        lecture.subjects.set([link.subject])


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
