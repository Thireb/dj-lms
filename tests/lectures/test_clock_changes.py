"""Times that do not exist because the clocks go forward (backlog P3-9).

The dates are found from today, so the tests do not go out of date.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from apps.accounts.models import User
from apps.core.tenancy import tenant_context
from apps.lectures.services import create_schedule
from apps.lectures.times import missing_time_message, wall_time_missing
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from tests.lectures.conftest import MEET_URL, schedule_details

LONDON = ZoneInfo("Europe/London")
NIGHT = time(1, 30)  # skipped in spring, twice in autumn (London)


def _next_day(missing: bool) -> date:
    """The next London day (from tomorrow) where 01:30 is skipped, or
    happens twice."""
    day = timezone.localdate() + timedelta(days=1)
    for _ in range(400):
        local = datetime.combine(day, NIGHT, tzinfo=LONDON)
        skipped = wall_time_missing(local)
        twice = local.utcoffset() != local.replace(fold=1).utcoffset()
        if skipped if missing else twice:
            return day
        day += timedelta(days=1)
    raise AssertionError("no clock change within 400 days")


def test_missing_and_twice_times() -> None:
    spring, autumn = _next_day(missing=True), _next_day(missing=False)
    assert wall_time_missing(datetime.combine(spring, NIGHT, tzinfo=LONDON))
    assert not wall_time_missing(datetime.combine(spring, time(3), tzinfo=LONDON))
    assert not wall_time_missing(datetime.combine(autumn, NIGHT, tzinfo=LONDON))
    karachi = ZoneInfo("Asia/Karachi")  # no clock changes
    assert not wall_time_missing(datetime.combine(spring, NIGHT, tzinfo=karachi))


def test_message_names_the_time_day_and_zone() -> None:
    spring = _next_day(missing=True)
    message = missing_time_message(datetime.combine(spring, NIGHT, tzinfo=LONDON))
    assert message.startswith("1:30 AM does not exist on ")
    assert "in Europe/London: the clocks go forward." in message


@pytest.mark.django_db
def test_schedule_refuses_a_skipped_time(school) -> None:
    spring = _next_day(missing=True)
    start = max(spring - timedelta(days=3), timezone.localdate() + timedelta(days=1))
    institute = school.morning.institute
    values = schedule_details(
        school,
        start_time=NIGHT,
        start_date=start,
        end_date=spring + timedelta(days=3),
        time_zone="Europe/London",
    )
    with tenant_context(institute), pytest.raises(ValidationError) as error:
        create_schedule(institute, values)
    assert "does not exist" in str(error.value.message_dict["start_time"])


@pytest.mark.django_db
def test_lecture_form_refuses_a_skipped_time(school, admin_client) -> None:
    spring = _next_day(missing=True)
    response = _post_lecture(school, admin_client, spring, "01:30")
    assert response.status_code == 200
    assert "does not exist on" in response.content.decode()


@pytest.mark.django_db
def test_lecture_form_takes_a_time_that_happens_twice(school, admin_client) -> None:
    autumn = _next_day(missing=False)
    response = _post_lecture(school, admin_client, autumn, "01:30")
    assert response.status_code == 302


def _post_lecture(school, client, day: date, start: str):
    user = User.objects.get(pk=client.session["_auth_user_id"])
    user.timezone = "Europe/London"
    user.save(update_fields=["timezone"])
    return client.post(
        reverse("admin:lecture_create"),
        {
            "title": "Night class",
            "teacher": school.teacher_1.pk,
            "batch_subjects": [f"{school.morning.pk}:{school.math.pk}"],
            "date": day.isoformat(),
            "start_time": start,
            "duration_minutes": "60",
            "delivery_mode": "manual_link",
            "meeting_url": MEET_URL,
            "description": "",
        },
    )
