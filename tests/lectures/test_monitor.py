"""Admin Lectures dashboard / Live lecture monitor (roadmap 3.6, SPEC 8)."""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.lectures.models import Lecture, LectureStatus
from apps.lectures.services import lecture_monitor
from apps.lectures.ui import minutes_text
from apps.lectures.views import LecturesDashboardPage
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from tests.conftest import cell, make_user, table_row
from tests.lectures.conftest import add_lecture, put_at, signed_in, soon

URL = reverse("admin:dashboard_lectures")


def _set(lecture: Lecture, **fields) -> Lecture:
    # unscoped: test set-up outside a tenant context.
    Lecture.unscoped.filter(pk=lecture.pk).update(**fields)
    lecture.refresh_from_db()
    return lecture


def _at(school, minutes: int, days: int, **fields) -> Lecture:
    """A lecture ``minutes`` from now; ``days`` keeps the services' overlap
    check apart before it is moved."""
    lecture = add_lecture(school, starts_at=soon(days=days), **fields)
    return put_at(lecture, timezone.now() + timedelta(minutes=minutes))


@pytest.fixture
def busy_day(school):
    """Live, late, soon, later and cancelled lectures, all today or now."""
    live = _set(
        _at(school, -20, 1, title="Live algebra"),
        status=LectureStatus.LIVE,
        started_at=timezone.now() - timedelta(minutes=18),
    )
    late = _at(school, -7, 2, title="Late algebra")
    soon_one = _at(
        school,
        45,
        3,
        title="Soon physics",
        teacher=school.teacher_2,
        batch=school.evening,
        subjects=[school.physics],
    )
    later = _at(school, 180, 4, title="Later algebra")
    dropped = _set(
        _at(school, 30, 5, title="Dropped algebra"),
        status=LectureStatus.CANCELLED,
    )
    return school, live, late, soon_one, later, dropped


# Service


@pytest.mark.django_db
def test_monitor_sorts_lectures_into_live_late_and_soon(busy_day) -> None:
    school, live, late, soon_one, later, dropped = busy_day
    admin = make_user(
        email="m@example.com",
        role=Role.INSTITUTE_ADMIN,
        institute=school.morning.institute,
    )

    data = lecture_monitor(admin)

    assert data.live == [live]
    assert data.late == [late]
    assert data.soon == [soon_one]
    assert later not in data.soon and dropped not in data.soon


@pytest.mark.django_db
def test_a_late_lecture_leaves_the_list_at_its_end(school) -> None:
    ended = _at(school, -70, 1, title="Never started")
    user = school.teacher_1.user

    assert ended not in lecture_monitor(user).late


@pytest.mark.django_db
def test_today_counts_by_status_without_cancelled_in_the_total(school) -> None:
    noon = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)
    for hour, days, status in (
        (8, 1, LectureStatus.SCHEDULED),
        (9, 2, LectureStatus.FINISHED),
        (10, 3, LectureStatus.CANCELLED),
    ):
        lecture = add_lecture(school, starts_at=soon(days=days))
        _set(put_at(lecture, noon.replace(hour=hour)), status=status)
    put_at(add_lecture(school, starts_at=soon(days=4)), noon + timedelta(days=1))

    with timezone.override("UTC"):
        data = lecture_monitor(school.teacher_1.user, now=noon)

    assert data.today == {"scheduled": 1, "finished": 1, "cancelled": 1}
    assert data.today_total == 2


@pytest.mark.django_db
def test_monitor_follows_for_user(busy_day) -> None:
    school = busy_day[0]

    data = lecture_monitor(school.teacher_2.user)

    assert data.live == data.late == []
    assert [lecture.title for lecture in data.soon] == ["Soon physics"]


def test_minutes_text() -> None:
    assert minutes_text(timedelta(seconds=30)) == "Just now"
    assert minutes_text(timedelta(minutes=25)) == "25 min"
    assert minutes_text(timedelta(minutes=65)) == "1 h 05 min"


# Page


@pytest.mark.django_db
def test_page_shows_the_numbers_and_three_lists(admin_client, busy_day) -> None:
    _, live, late, soon_one, *_ = busy_day

    html = admin_client.get(URL).content.decode()

    assert re.search(r">1</p><p[^>]*>Live now<", html)
    assert re.search(r">1</p><p[^>]*>Late start<", html)
    assert re.search(r">1</p><p[^>]*>Next 2 hours<", html)
    assert "1 finished" not in html and "0 finished, 0 not held, 1 cancelled" in html
    assert cell(table_row(html, "Live algebra"), "wait") == ["18", "min"]
    assert cell(table_row(html, "Late algebra"), "wait") == ["7", "min"]
    assert cell(table_row(html, "Soon physics"), "wait") in (
        ["44", "min"],
        ["45", "min"],
    )
    assert "Later algebra" not in html and "Dropped algebra" not in html
    detail = reverse("admin:lecture_detail", kwargs={"pk": late.pk})
    assert f'href="{detail}"' in html


@pytest.mark.django_db
def test_page_reloads_its_panel_every_30_seconds(admin_client) -> None:
    html = admin_client.get(URL).content.decode()

    assert (
        f'id="lecture-monitor" class="live-region" hx-get="{URL}" '
        'hx-trigger="every 30s" hx-select="#lecture-monitor" hx-swap="outerHTML"'
    ) in html
    assert "No lecture is live now." in html
    assert "No lecture is late." in html
    assert "Nothing starts in the next 2 hours." in html


@pytest.mark.django_db
def test_page_is_for_admins_with_the_dashboards_menu(institute_a) -> None:
    user = make_user(
        email="sub@example.com", role=Role.SUB_ADMIN, institute=institute_a
    )
    request = RequestFactory().get(URL)
    request.user, request.institute = user, institute_a

    user.allowed_menus = ["dashboards"]
    with tenant_context(institute_a):
        allowed = LecturesDashboardPage.as_view()(request)
    user.allowed_menus = ["online_lectures"]
    denied = LecturesDashboardPage.as_view()(request)

    assert allowed.status_code == 200
    assert denied.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("role", [Role.TEACHER, Role.STUDENT, Role.GUARDIAN])
def test_other_roles_get_403(institute_a, role) -> None:
    client = signed_in(
        make_user(email="x@example.com", role=role, institute=institute_a)
    )

    assert client.get(URL).status_code == 403


@pytest.mark.django_db
def test_other_institute_sees_nothing(busy_day, institute_b) -> None:
    client = signed_in(
        make_user(
            email="b@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_b
        )
    )

    html = client.get(URL).content.decode()

    assert "Live algebra" not in html and "Late algebra" not in html


@pytest.mark.django_db
def test_main_dashboard_links_to_the_monitor_and_add_lecture(admin_client) -> None:
    html = admin_client.get(reverse("admin:home")).content.decode()

    assert f'href="{URL}"' in html
    assert f'href="{reverse("admin:lecture_create")}"' in html
