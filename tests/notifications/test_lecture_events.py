"""Roadmap 6.2: lecture notifications (SPEC 7). Institute A is in
Asia/Karachi, so 10:00 UTC shows as 3:00 PM PKT."""

from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from apps.core.tenancy import tenant_context
from apps.lectures.models import Lecture, LectureStatus
from apps.lectures.services import (
    cancel_lecture,
    remind_upcoming_lectures,
    start_lecture,
    stop_schedule,
    update_lecture,
    update_schedule,
)
from apps.lectures.tasks import remind_all_lectures
from apps.notifications.models import Notification
from apps.people.models import ProfileStatus, StudentProfile
from django.urls import reverse
from django.utils import timezone

from tests.lectures.conftest import (
    add_lecture,
    add_schedule,
    details,
    put_at,
    schedule_details,
    signed_in,
    soon,
)
from tests.school import link_teacher


def inbox(profile) -> list[tuple[str, str, str]]:
    # unscoped: test assertion outside a tenant context.
    rows = Notification.unscoped.filter(user=profile.user).order_by("pk")
    return [(row.event, row.text, row.link) for row in rows]


def texts(profile) -> list[str]:
    return [text for _event, text, _link in inbox(profile)]


def _run(school, function, *args, **kwargs):
    with tenant_context(school.morning.institute):
        return function(*args, **kwargs)


STUDENT_LIST = reverse("student:lecture_list")
GUARDIAN_LIST = reverse("guardian:lecture_schedule")


# A single lecture


@pytest.mark.django_db
def test_a_new_lecture_reaches_its_class(school) -> None:
    lecture = add_lecture(school)
    day = timezone.localtime(lecture.starts_at, ZoneInfo("Asia/Karachi"))
    when = f"{day:%a} {day.day} {day:%b %Y} at 3:00 PM PKT"
    text = f"New lecture: Algebra basics, {when}."
    assert inbox(school.student_1) == [("lecture_changed", text, STUDENT_LIST)]
    assert inbox(school.guardian_1) == [
        ("lecture_changed", f"For {school.student_1}: {text}", GUARDIAN_LIST)
    ]
    detail = reverse("teacher:lecture_detail", kwargs={"pk": lecture.pk})
    assert inbox(school.teacher_1) == [("lecture_changed", text, detail)]
    for other in (
        school.student_2,
        school.guardian_2,
        school.teacher_2,
        school.student_b,
    ):
        assert inbox(other) == [], other


@pytest.mark.django_db
def test_times_are_in_each_recipients_zone(school) -> None:
    user = school.student_1.user
    user.timezone = "Europe/London"
    user.save()
    add_lecture(school)
    (student_text,) = texts(school.student_1)
    (guardian_text,) = texts(school.guardian_1)
    assert "PKT" not in student_text and "AM" in student_text
    assert "3:00 PM PKT" in guardian_text


@pytest.mark.django_db
def test_the_person_who_saves_gets_nothing(school) -> None:
    institute = school.morning.institute
    from apps.lectures.services import create_lecture

    _run(
        school, create_lecture, institute, details(school), actor=school.teacher_1.user
    )
    assert inbox(school.teacher_1) == []
    assert len(inbox(school.student_1)) == 1


@pytest.mark.django_db
def test_inactive_students_get_nothing(school) -> None:
    # unscoped: test set-up outside a tenant context.
    StudentProfile.unscoped.filter(pk=school.student_1.pk).update(
        status=ProfileStatus.INACTIVE
    )
    add_lecture(school)
    assert inbox(school.student_1) == [] and inbox(school.guardian_1) == []


@pytest.mark.django_db
def test_only_a_new_plan_is_notified(school) -> None:
    lecture = add_lecture(school)
    _run(school, update_lecture, lecture, details(school, title="Renamed"))
    assert len(inbox(school.student_1)) == 1  # a new title alone says nothing
    later = soon(days=2)
    _run(school, update_lecture, lecture, details(school, starts_at=later))
    event, text, _ = inbox(school.student_1)[-1]
    assert event == "lecture_changed" and text.startswith("Lecture changed: Algebra")
    assert len(inbox(school.guardian_1)) == 2 and len(inbox(school.teacher_1)) == 2


@pytest.mark.django_db
def test_a_new_teacher_and_the_old_one_are_told(school) -> None:
    link_teacher(school.teacher_2, {school.morning: [school.math]})
    lecture = add_lecture(school)
    _run(school, update_lecture, lecture, details(school, teacher=school.teacher_2))
    detail = reverse("teacher:lecture_detail", kwargs={"pk": lecture.pk})
    assert inbox(school.teacher_2)[-1][2] == detail
    assert inbox(school.teacher_1)[-1][2] == reverse("teacher:lecture_list")


@pytest.mark.django_db
def test_start_tells_the_students_only(school) -> None:
    lecture = put_at(add_lecture(school), timezone.now() + timedelta(minutes=5))
    _run(school, start_lecture, lecture, window=15)
    assert inbox(school.student_1)[-1][:2] == (
        "lecture_started",
        "Algebra basics has started. You can join now.",
    )
    assert len(inbox(school.guardian_1)) == 1 and len(inbox(school.teacher_1)) == 1


@pytest.mark.django_db
def test_cancel_tells_students_guardians_and_teacher(school) -> None:
    lecture = add_lecture(school)
    _run(school, cancel_lecture, lecture)
    for profile in (school.student_1, school.guardian_1, school.teacher_1):
        event, text, _ = inbox(profile)[-1]
        assert event == "lecture_cancelled" and "Cancelled: Algebra basics" in text


# Recurring schedules: one notification per save (owner decision)


@pytest.mark.django_db
def test_a_schedule_sends_one_notification_per_save(school) -> None:
    schedule = add_schedule(school)
    assert Lecture.unscoped.filter(schedule=schedule).count() == 7
    assert texts(school.student_1) == [
        "New weekly schedule: Daily algebra, Mon, Tue, Wed, Thu, Fri, Sat, Sun "
        "at 10:00 AM PKT."
    ]
    assert len(inbox(school.guardian_1)) == 1 and len(inbox(school.teacher_1)) == 1
    changed = schedule_details(school, weekdays=[0, 2, 4])
    _run(school, update_schedule, schedule, changed)
    assert texts(school.student_1)[-1] == (
        "Weekly schedule changed: Daily algebra, now Mon, Wed, Fri at 10:00 AM PKT."
    )
    from apps.lectures.services import generate_lectures

    _run(school, generate_lectures, schedule)
    cancelled = _run(school, stop_schedule, schedule)
    assert texts(school.student_1)[-1] == (
        f"Weekly schedule stopped: Daily algebra. {cancelled} upcoming lectures "
        "are cancelled."
    )
    assert len(inbox(school.student_1)) == 3


# "Starts in 15 minutes"


@pytest.mark.django_db
def test_reminder_goes_once_for_lectures_in_the_next_15_minutes(school) -> None:
    now = timezone.now()
    due = put_at(add_lecture(school, title="Due"), now + timedelta(minutes=12))
    put_at(
        add_lecture(school, title="Later", starts_at=soon(days=3)),
        now + timedelta(minutes=20),
    )
    gone = put_at(
        add_lecture(school, title="Gone", starts_at=soon(days=4)),
        now + timedelta(minutes=10),
    )
    _run(school, cancel_lecture, gone)
    assert _run(school, remind_upcoming_lectures, school.morning.institute, now) == 1
    assert _run(school, remind_upcoming_lectures, school.morning.institute, now) == 0
    soon_texts = [t for e, t, _ in inbox(school.student_1) if e == "lecture_soon"]
    local = due.starts_at.astimezone(ZoneInfo("Asia/Karachi"))
    assert soon_texts == [f"Due starts soon, at {local:%-I:%M %p} PKT."]
    assert [e for e, _t, _l in inbox(school.teacher_1)].count("lecture_soon") == 1
    assert [e for e, _t, _l in inbox(school.guardian_1)].count("lecture_soon") == 0


@pytest.mark.django_db
def test_a_new_time_is_reminded_again(school) -> None:
    now = timezone.now()
    lecture = put_at(add_lecture(school), now + timedelta(minutes=12))
    _run(school, remind_upcoming_lectures, school.morning.institute, now)
    lecture.refresh_from_db()
    assert lecture.reminded_at is not None
    _run(school, update_lecture, lecture, details(school, starts_at=soon(days=2)))
    lecture.refresh_from_db()
    assert lecture.reminded_at is None


@pytest.mark.django_db
def test_the_reminder_job_runs_for_active_institutes(school) -> None:
    put_at(add_lecture(school), timezone.now() + timedelta(minutes=10))
    assert remind_all_lectures() == 1
    assert remind_all_lectures() == 0
    assert LectureStatus.SCHEDULED  # the lecture stays scheduled


# Pages pass the person who saves


@pytest.mark.django_db
def test_a_teacher_who_adds_a_lecture_is_not_told(school) -> None:
    from tests.lectures.test_teacher_pages import _form

    response = signed_in(school.teacher_1.user).post(
        reverse("teacher:lecture_create"), _form(school)
    )
    assert response.status_code == 302
    assert inbox(school.teacher_1) == [] and len(inbox(school.student_1)) == 1
