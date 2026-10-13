"""Teacher Schedule calendar (roadmap 3.3, SPEC 3)."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from apps.core.roles import Role
from apps.lectures.models import LectureStatus
from apps.lectures.services import calendar_lectures, calendar_range
from apps.lectures.views import calendar_day, calendar_label
from django.urls import reverse
from django.utils import timezone

from tests.conftest import make_user
from tests.lectures.conftest import (
    KARACHI,
    add_lecture,
    karachi_today,
    put_at,
    signed_in,
)

URL = reverse("teacher:schedule")


def _karachi(day: date, hour: int) -> datetime:
    return datetime.combine(day, time(hour), tzinfo=ZoneInfo(KARACHI))


# Ranges


def test_week_starts_on_monday() -> None:
    span = calendar_range("week", date(2026, 10, 15))  # a Thursday

    assert (span.first, span.last) == (date(2026, 10, 12), date(2026, 10, 18))
    assert (span.previous, span.next) == (date(2026, 10, 5), date(2026, 10, 19))
    assert span.month is None
    assert len(span.days) == 7


def test_month_shows_whole_weeks() -> None:
    span = calendar_range("month", date(2026, 10, 15))

    assert span.month == date(2026, 10, 1)
    assert (span.first, span.last) == (date(2026, 9, 28), date(2026, 11, 1))
    assert (span.previous, span.next) == (date(2026, 9, 1), date(2026, 11, 1))
    assert len(span.days) == 35


def test_month_across_the_year_end() -> None:
    span = calendar_range("month", date(2026, 12, 31))

    assert (span.previous, span.next) == (date(2026, 11, 1), date(2027, 1, 1))
    assert span.last == date(2027, 1, 3)


def test_labels() -> None:
    assert calendar_label(calendar_range("month", date(2026, 10, 3))) == (
        "October 2026"
    )
    assert calendar_label(calendar_range("week", date(2026, 10, 1))) == (
        "28 Sep to 4 Oct 2026"
    )
    assert calendar_label(calendar_range("week", date(2026, 12, 31))) == (
        "28 Dec 2026 to 3 Jan 2027"
    )


@pytest.mark.parametrize(
    "value", ["", "x", "2026-13-01", "0001-01-03", "9999-12-30", None]
)
def test_bad_date_values_are_refused(value) -> None:
    assert calendar_day(value) is None


def test_good_date_value() -> None:
    assert calendar_day("2026-10-14") == date(2026, 10, 14)


# Lectures in range


@pytest.mark.django_db
def test_calendar_lectures_uses_the_viewer_date(school) -> None:
    """A lecture at 01:00 Karachi is on the previous day in UTC."""
    day = karachi_today() + timedelta(days=3)
    early = put_at(add_lecture(school, title="Early"), _karachi(day, 1))
    put_at(add_lecture(school, title="Next day"), _karachi(day + timedelta(1), 1))

    with timezone.override(ZoneInfo(KARACHI)):
        found = calendar_lectures(school.teacher_1.user, day, day)

    assert found == [early]


@pytest.mark.django_db
def test_calendar_lectures_follow_for_user(school) -> None:
    day = karachi_today() + timedelta(days=3)
    put_at(add_lecture(school), _karachi(day, 10))

    with timezone.override(ZoneInfo(KARACHI)):
        assert calendar_lectures(school.teacher_2.user, day, day) == []


# Page


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role", [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN, Role.STUDENT, Role.GUARDIAN]
)
def test_other_roles_get_403(institute_a, role) -> None:
    client = signed_in(
        make_user(email="x@example.com", role=role, institute=institute_a)
    )

    assert client.get(URL).status_code == 403


def _page(school, **params) -> str:
    response = signed_in(school.teacher_1.user).get(URL, params)
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
def test_week_page_shows_own_lectures_with_edit_links(school) -> None:
    day = karachi_today() + timedelta(days=1)
    mine = put_at(add_lecture(school, title="Algebra"), _karachi(day, 15))
    put_at(
        add_lecture(
            school,
            title="Other physics",
            teacher=school.teacher_2,
            batch=school.evening,
            subjects=[school.physics],
        ),
        _karachi(day, 15),
    )

    html = _page(school, date=day.isoformat())

    assert "Algebra" in html
    assert "Other physics" not in html
    assert "3:00 PM to 4:00 PM PKT" in html
    assert "Morning · Math" in html
    edit = reverse("teacher:lecture_edit", kwargs={"pk": mine.pk})
    assert f'<a href="{edit}"' in html
    assert re.search(r'href="\?view=week[^"]*"[^>]*aria-current="page"', html)
    assert re.search(rf'href="{URL}"[^>]*aria-current="page"', html), (
        "the Schedule menu item is active"
    )


@pytest.mark.django_db
def test_cancelled_lecture_has_no_link(school) -> None:
    day = karachi_today() + timedelta(days=1)
    lecture = put_at(add_lecture(school, title="Dropped"), _karachi(day, 15))
    lecture.status = LectureStatus.CANCELLED
    lecture.save(update_fields=["status"])

    html = _page(school, date=day.isoformat())

    edit = reverse("teacher:lecture_edit", kwargs={"pk": lecture.pk})
    assert edit not in html
    assert "Cancelled" in html


@pytest.mark.django_db
def test_month_page_and_navigation(school) -> None:
    html = _page(school, view="month", date="2026-10-20")

    assert "October 2026" in html
    assert 'href="?view=month&amp;date=2026-09-01"' in html
    assert 'href="?view=month&amp;date=2026-11-01"' in html
    assert "No lectures this month." in html


@pytest.mark.django_db
def test_unknown_view_and_bad_date_fall_back_to_this_week(school) -> None:
    today = karachi_today()

    html = _page(school, view="year", date="nope")

    monday = today - timedelta(days=today.weekday())
    assert f"{monday.day} " in html
    assert 'aria-current="date"' in html
    assert "calendar-week" in html


@pytest.mark.django_db
def test_week_page_puts_a_lecture_on_the_viewer_date(school) -> None:
    """01:00 Karachi is 20:00 UTC the day before; the card is the Karachi day."""
    day = karachi_today() + timedelta(days=2)
    put_at(add_lecture(school, title="Early"), _karachi(day, 1))

    html = _page(school, date=day.isoformat())

    cards = html.split('class="calendar-day ')[1:]
    early = [card for card in cards if "Early" in card]
    assert len(early) == 1
    assert f">{day.strftime('%a')} {day.day} {day.strftime('%b')}</h3>" in early[0]
