"""Lecture states, the lecture page, Start / End / Cancel and Lecture
history (roadmap 3.5, SPEC 3 and 6.4)."""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from apps.core.roles import Role
from apps.core.tenancy import TenantContextError, tenant_context
from apps.lectures.models import DeliveryMode, Lecture, LectureStatus
from apps.lectures.services import (
    can_start,
    cancel_lecture,
    end_lecture,
    finish_ended_lectures,
    list_history,
    start_lecture,
    taught_minutes,
    update_schedule,
)
from apps.lectures.tasks import finish_all_ended_lectures
from apps.lectures.views import AdminLectureHistoryPage
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from tests.conftest import cell, make_user, table_row
from tests.lectures.conftest import (
    add_lecture,
    add_schedule,
    put_at,
    schedule_details,
    schedule_lectures,
    signed_in,
    soon,
)

WINDOW = 10


def _set(lecture: Lecture, **fields) -> Lecture:
    # unscoped: test set-up outside a tenant context.
    Lecture.unscoped.filter(pk=lecture.pk).update(**fields)
    lecture.refresh_from_db()
    return lecture


def _in(school, minutes: int, **fields) -> Lecture:
    """A lecture that starts ``minutes`` from now (negative: started)."""
    starts = timezone.now() + timedelta(minutes=minutes)
    return put_at(add_lecture(school, **fields), starts)


def _run(school, call, *args, **kwargs):
    with tenant_context(school.morning.institute):
        return call(*args, **kwargs)


def _url(portal: str, action: str, lecture: Lecture) -> str:
    return reverse(f"{portal}:lecture_{action}", kwargs={"pk": lecture.pk})


# Start


@pytest.mark.django_db
def test_start_is_open_from_the_window_until_the_end(school) -> None:
    lecture = add_lecture(school)
    start = lecture.starts_at

    def ok(at) -> bool:
        return can_start(lecture, now=at, window=WINDOW)

    assert not ok(start - timedelta(minutes=11))
    assert ok(start - timedelta(minutes=10))
    assert ok(start + timedelta(minutes=59))
    assert not ok(start + timedelta(minutes=60))
    lecture.status = LectureStatus.CANCELLED
    assert not ok(start)


@pytest.mark.django_db
def test_start_sets_live_and_the_time(school) -> None:
    lecture = _in(school, 5)

    started = _run(school, start_lecture, lecture, window=WINDOW)

    lecture.refresh_from_db()
    assert started.status == lecture.status == LectureStatus.LIVE
    assert lecture.started_at is not None


@pytest.mark.django_db
def test_start_is_refused_early_and_twice(school) -> None:
    early = _in(school, 30)
    live = _set(_in(school, 2, starts_at=soon(days=2)), status=LectureStatus.LIVE)

    for lecture in (early, live):
        with pytest.raises(ValidationError, match="Only a scheduled lecture"):
            _run(school, start_lecture, lecture, window=WINDOW)
    early.refresh_from_db()
    assert early.status == LectureStatus.SCHEDULED


# End


@pytest.mark.django_db
def test_end_finishes_a_live_lecture(school) -> None:
    lecture = _set(_in(school, -20), status=LectureStatus.LIVE)
    now = timezone.now()

    _run(school, end_lecture, lecture, now=now)

    lecture.refresh_from_db()
    assert lecture.status == LectureStatus.FINISHED
    assert lecture.ended_at == now


@pytest.mark.django_db
def test_end_needs_a_live_lecture(school) -> None:
    lecture = _in(school, -20)

    with pytest.raises(ValidationError, match="Only a live lecture"):
        _run(school, end_lecture, lecture)


# Cancel


@pytest.mark.django_db
def test_cancel_a_scheduled_lecture(school) -> None:
    lecture = add_lecture(school)

    _run(school, cancel_lecture, lecture)

    lecture.refresh_from_db()
    assert lecture.status == LectureStatus.CANCELLED
    assert lecture.follows_schedule is False


@pytest.mark.django_db
@pytest.mark.parametrize("status", [LectureStatus.LIVE, LectureStatus.FINISHED])
def test_cancel_is_refused_once_started(school, status) -> None:
    lecture = _set(add_lecture(school), status=status)

    with pytest.raises(ValidationError, match="Only a scheduled lecture"):
        _run(school, cancel_lecture, lecture)


@pytest.mark.django_db
def test_cancel_is_refused_after_the_end(school) -> None:
    lecture = _in(school, -120)

    with pytest.raises(ValidationError):
        _run(school, cancel_lecture, lecture)


@pytest.mark.django_db
def test_schedule_edit_keeps_a_cancelled_lecture(school) -> None:
    schedule = add_schedule(school)
    first = schedule_lectures(schedule)[0]
    _run(school, cancel_lecture, first)

    _run(
        school,
        update_schedule,
        schedule,
        schedule_details(school, title="Renamed"),
    )

    first.refresh_from_db()
    assert first.status == LectureStatus.CANCELLED
    assert first.title == "Daily algebra"


# Finish on their own


@pytest.mark.django_db
def test_lectures_past_their_end_become_finished(school) -> None:
    missed = _in(school, -120, title="Missed")
    ran = _set(
        _in(school, -90, title="Ran", starts_at=soon(days=2)),
        status=LectureStatus.LIVE,
    )
    running = _set(
        _in(school, -30, title="Running", starts_at=soon(days=3)),
        status=LectureStatus.LIVE,
    )
    dropped = _set(
        _in(school, -200, title="Dropped", starts_at=soon(days=4)),
        status=LectureStatus.CANCELLED,
    )

    count = _run(school, finish_ended_lectures, school.morning.institute)

    for lecture in (missed, ran, running, dropped):
        lecture.refresh_from_db()
    assert count == 2
    assert missed.status == ran.status == LectureStatus.FINISHED
    assert missed.ended_at == missed.ends_at
    assert running.status == LectureStatus.LIVE
    assert dropped.status == LectureStatus.CANCELLED


@pytest.mark.django_db
def test_finish_needs_a_tenant_context(institute_a) -> None:
    with pytest.raises(TenantContextError):
        finish_ended_lectures(institute_a)


@pytest.mark.django_db
def test_finish_task_runs_for_active_institutes(school, institute_b) -> None:
    missed = _in(school, -120)
    institute_b.is_active = False
    institute_b.save(update_fields=["is_active"])

    assert finish_all_ended_lectures() == 1
    missed.refresh_from_db()
    assert missed.status == LectureStatus.FINISHED


def test_taught_minutes_uses_start_and_end_when_known() -> None:
    start = timezone.now()
    lecture = Lecture(duration_minutes=60)

    assert taught_minutes(lecture) == 60
    lecture.started_at, lecture.ended_at = start, start + timedelta(minutes=47)
    assert taught_minutes(lecture) == 47


# Lecture page


@pytest.mark.django_db
def test_admin_lecture_page_shows_details_and_cancel(admin_client, school) -> None:
    lecture = add_lecture(school, description="Bring a ruler.")

    html = admin_client.get(_url("admin", "detail", lecture)).content.decode()

    assert "Algebra basics" in html
    assert "Bring a ruler." in html
    assert re.search(r"<dt[^>]*>Teacher</dt>", html)
    assert f'action="{_url("admin", "cancel", lecture)}"' in html
    assert ">Keep lecture<" in html
    assert f'href="{_url("admin", "edit", lecture)}"' in html


@pytest.mark.django_db
def test_admin_lecture_page_of_a_finished_lecture(admin_client, school) -> None:
    start = timezone.now() - timedelta(days=1)
    lecture = _set(
        put_at(add_lecture(school), start),
        status=LectureStatus.FINISHED,
        started_at=start,
        ended_at=start + timedelta(minutes=50),
    )

    html = admin_client.get(_url("admin", "detail", lecture)).content.decode()

    assert ">50 min<" in html
    assert _url("admin", "cancel", lecture) not in html
    assert _url("admin", "edit", lecture) not in html


@pytest.mark.django_db
def test_teacher_lecture_page_has_start_then_end(school) -> None:
    lecture = _in(school, 5)
    client = signed_in(school.teacher_1.user)

    before = client.get(_url("teacher", "detail", lecture)).content.decode()
    _set(lecture, status=LectureStatus.LIVE)
    during = client.get(_url("teacher", "detail", lecture)).content.decode()

    assert f'action="{_url("teacher", "start", lecture)}"' in before
    assert "/cancel/" not in before
    assert f'action="{_url("teacher", "end", lecture)}"' in during
    assert "<dt" in during and ">Teacher</dt>" not in during


@pytest.mark.django_db
def test_lecture_page_is_scoped(admin_client, school, institute_b) -> None:
    lecture = add_lecture(school)
    other_admin = signed_in(
        make_user(
            email="b@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_b
        )
    )

    assert other_admin.get(_url("admin", "detail", lecture)).status_code == 404
    assert (
        signed_in(school.teacher_2.user)
        .get(_url("teacher", "detail", lecture))
        .status_code
        == 404
    )
    assert (
        signed_in(school.student_1.user)
        .get(_url("admin", "detail", lecture))
        .status_code
        == 403
    )


# Start, End and Cancel views


@pytest.mark.django_db
def test_start_view_starts_and_says_so(school) -> None:
    lecture = _in(school, 5)

    response = signed_in(school.teacher_1.user).post(
        _url("teacher", "start", lecture), follow=True
    )

    lecture.refresh_from_db()
    assert response.redirect_chain[-1][0] == _url("teacher", "detail", lecture)
    assert "Algebra basics started. Students can join now." in response.content.decode()
    assert lecture.status == LectureStatus.LIVE


@pytest.mark.django_db
def test_start_view_shows_the_refusal(school) -> None:
    lecture = _in(school, 60)

    response = signed_in(school.teacher_1.user).post(
        _url("teacher", "start", lecture), follow=True
    )

    lecture.refresh_from_db()
    assert "Only a scheduled lecture can be started" in response.content.decode()
    assert lecture.status == LectureStatus.SCHEDULED


@pytest.mark.django_db
def test_state_views_need_post_the_owner_and_the_role(school) -> None:
    lecture = _in(school, 5)
    owner = signed_in(school.teacher_1.user)

    assert owner.get(_url("teacher", "start", lecture)).status_code == 405
    assert (
        signed_in(school.teacher_2.user)
        .post(_url("teacher", "start", lecture))
        .status_code
        == 404
    )
    assert owner.post(_url("admin", "cancel", lecture)).status_code == 403
    lecture.refresh_from_db()
    assert lecture.status == LectureStatus.SCHEDULED


@pytest.mark.django_db
def test_end_view(school) -> None:
    lecture = _set(_in(school, -20), status=LectureStatus.LIVE)

    response = signed_in(school.teacher_1.user).post(
        _url("teacher", "end", lecture), follow=True
    )

    lecture.refresh_from_db()
    assert lecture.status == LectureStatus.FINISHED
    assert "Algebra basics ended." in response.content.decode()


@pytest.mark.django_db
def test_cancel_view(admin_client, school) -> None:
    lecture = add_lecture(school)

    response = admin_client.post(_url("admin", "cancel", lecture), follow=True)

    lecture.refresh_from_db()
    assert lecture.status == LectureStatus.CANCELLED
    assert "Algebra basics cancelled." in response.content.decode()


# Lists


@pytest.mark.django_db
def test_list_rows_have_view_cancel_and_start(admin_client, school) -> None:
    lecture = _in(school, 5)

    admin = admin_client.get(reverse("admin:lecture_list")).content.decode()
    teacher = signed_in(school.teacher_1.user).get(reverse("teacher:lecture_list"))
    teacher = teacher.content.decode()

    admin_row = table_row(admin, "Algebra basics")
    teacher_row = table_row(teacher, "Algebra basics")
    assert f'href="{_url("admin", "detail", lecture)}"' in admin_row
    assert f'action="{_url("admin", "cancel", lecture)}"' in admin_row
    assert f'action="{_url("teacher", "start", lecture)}"' in teacher_row
    assert "cancel" not in teacher_row


@pytest.mark.django_db
def test_join_works_once_the_teacher_starts(school) -> None:
    lecture = _in(school, 5)
    signed_in(school.teacher_1.user).post(_url("teacher", "start", lecture))

    response = signed_in(school.student_1.user).post(_url("student", "join", lecture))

    assert response.status_code == 302
    assert response["Location"] == lecture.meeting_url


# History


def _finished(school, days: int, **fields) -> Lecture:
    lecture = add_lecture(school, starts_at=soon(days=days), **fields)
    return _set(
        put_at(lecture, timezone.now() - timedelta(days=days)),
        status=LectureStatus.FINISHED,
    )


@pytest.mark.django_db
def test_history_lists_finished_lectures_newest_first(school) -> None:
    older = _finished(school, 5, title="Older")
    newer = _finished(school, 2, title="Newer")
    add_lecture(school, title="Coming")
    _finished(
        school,
        3,
        title="Physics",
        teacher=school.teacher_2,
        batch=school.evening,
        subjects=[school.physics],
    )

    assert list(list_history(school.teacher_1.user)) == [newer, older]
    assert len(list_history(school.student_1.user)) == 2


@pytest.mark.django_db
def test_teacher_history_page(school) -> None:
    _finished(school, 2, title="Done algebra", delivery_mode=DeliveryMode.MANUAL_LINK)

    html = signed_in(school.teacher_1.user).get(reverse("teacher:lecture_history"))
    html = html.content.decode()

    row = table_row(html, "Done algebra")
    assert cell(row, "duration") == ["60", "min"]
    assert cell(row, "attendance") == ["Not", "taken"]
    assert "cell-teacher" not in html
    assert '<select name="batch"' in html
    assert re.search(
        rf'href="{reverse("teacher:lecture_history")}"[^>]*aria-current="page"', html
    )


@pytest.mark.django_db
def test_admin_history_filters_by_teacher(admin_client, school) -> None:
    _finished(school, 2, title="Done algebra")
    _finished(
        school,
        3,
        title="Done physics",
        teacher=school.teacher_2,
        batch=school.evening,
        subjects=[school.physics],
    )
    url = reverse("admin:teacher_lecture_history")

    html = admin_client.get(url, {"teacher": school.teacher_2.pk}).content.decode()

    assert "Done physics" in html and "Done algebra" not in html
    assert "cell-teacher" in html


@pytest.mark.django_db
def test_admin_history_needs_the_people_menu(institute_a) -> None:
    user = make_user(
        email="sub@example.com", role=Role.SUB_ADMIN, institute=institute_a
    )
    request = RequestFactory().get("/admin/teachers/lecture-history/")
    request.user, request.institute = user, institute_a

    user.allowed_menus = ["people"]
    with tenant_context(institute_a):
        allowed = AdminLectureHistoryPage.as_view()(request)
    user.allowed_menus = ["online_lectures"]
    denied = AdminLectureHistoryPage.as_view()(request)

    assert allowed.status_code == 200
    assert denied.status_code == 403


@pytest.mark.django_db
def test_teacher_list_links_to_their_lecture_history(admin_client, school) -> None:
    html = admin_client.get(reverse("admin:teacher_list")).content.decode()

    url = reverse("admin:teacher_lecture_history")
    assert f'href="{url}?teacher={school.teacher_1.pk}"' in html


@pytest.mark.django_db
@pytest.mark.parametrize("status", [LectureStatus.FINISHED, LectureStatus.CANCELLED])
def test_closed_lecture_has_no_meeting_link(admin_client, school, status) -> None:
    lecture = _set(add_lecture(school), status=status)

    page = admin_client.get(_url("admin", "detail", lecture)).content.decode()
    rows = admin_client.get(reverse("admin:lecture_list"), {"show": "all"})

    assert lecture.meeting_url not in page
    assert lecture.meeting_url not in rows.content.decode()
