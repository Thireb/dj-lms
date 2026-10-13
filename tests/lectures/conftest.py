"""Helpers for lecture tests. Fake names and links only."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.lectures.models import DeliveryMode, Lecture, RecurringSchedule
from apps.lectures.services import (
    LectureDetails,
    ScheduleDetails,
    create_lecture,
    create_schedule,
    generate_lectures,
)
from django.test import Client
from django.utils import timezone

from tests.conftest import make_user

MEET_URL = "https://meet.example.com/abc-defg-hij"


def soon(days: int = 1, hour: int = 10) -> datetime:
    """A whole hour some days ahead, in UTC."""
    day = timezone.now() + timedelta(days=days)
    return day.replace(hour=hour, minute=0, second=0, microsecond=0)


def details(school, **fields) -> LectureDetails:
    """Teacher 1, Morning batch, Math, an hour from tomorrow 10:00 UTC."""
    values = {
        "title": "Algebra basics",
        "teacher": school.teacher_1,
        "batch": school.morning,
        "subjects": [school.math],
        "starts_at": soon(),
        "duration_minutes": 60,
        "delivery_mode": DeliveryMode.MANUAL_LINK,
        "meeting_url": MEET_URL,
    }
    values.update(fields)
    return LectureDetails(**values)


def add_lecture(school, **fields) -> Lecture:
    with tenant_context(school.morning.institute):
        return create_lecture(
            school.morning.institute, details(school, **fields)
        ).lecture


def put_at(lecture: Lecture, starts_at: datetime) -> Lecture:
    """Move a lecture into the past, which the services refuse to do."""
    # unscoped: test set-up outside a tenant context.
    Lecture.unscoped.filter(pk=lecture.pk).update(starts_at=starts_at)
    lecture.refresh_from_db()
    return lecture


def select_values(html: str, name: str) -> list[str]:
    """The option values of one select. Check a pk inside its own select:
    the pks of other tables can have the same number."""
    match = re.search(rf'<select name="{name}".*?</select>', html, re.S)
    assert match, name
    return re.findall(r'<option value="([^"]*)"', match.group(0))


def signed_in(user) -> Client:
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def admin_client(institute_a) -> Client:
    return signed_in(
        make_user(
            email="admin-a@example.com",
            role=Role.INSTITUTE_ADMIN,
            institute=institute_a,
        )
    )


KARACHI = "Asia/Karachi"
EVERY_DAY = [0, 1, 2, 3, 4, 5, 6]


def karachi_today() -> date:
    return timezone.localtime(timezone.now(), ZoneInfo(KARACHI)).date()


def schedule_details(school, **fields) -> ScheduleDetails:
    """Teacher 1, Morning/Math, every day 10:00 Karachi, for 7 days from
    tomorrow."""
    start = karachi_today() + timedelta(days=1)
    values = {
        "title": "Daily algebra",
        "teacher": school.teacher_1,
        "batch": school.morning,
        "subjects": [school.math],
        "weekdays": EVERY_DAY,
        "start_time": time(10, 0),
        "duration_minutes": 60,
        "start_date": start,
        "end_date": start + timedelta(days=6),
        "time_zone": KARACHI,
        "delivery_mode": DeliveryMode.MANUAL_LINK,
        "meeting_url": MEET_URL,
    }
    values.update(fields)
    return ScheduleDetails(**values)


def add_schedule(school, **fields) -> RecurringSchedule:
    """Create a schedule and make its lectures (the task runs after commit,
    which a test transaction never reaches, so call the service here)."""
    institute = school.morning.institute
    with tenant_context(institute):
        schedule = create_schedule(institute, schedule_details(school, **fields))
        generate_lectures(schedule)
    schedule.refresh_from_db()
    return schedule


def schedule_lectures(schedule: RecurringSchedule) -> list[Lecture]:
    # unscoped: test assertion outside a tenant context.
    return list(Lecture.unscoped.filter(schedule=schedule).order_by("starts_at"))
