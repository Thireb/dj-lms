"""Lecture notifications (roadmap 6.2, SPEC 7). The lecture services call
these inside their transaction, so a change that fails sends nothing.

Times in the texts are each recipient's local time (``notify`` runs the
text in their time zone). A recurring schedule sends one notification per
save, not one per lecture (owner decision 2026-10-16)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from django.urls import reverse
from django.utils.dateformat import format as date_format

from apps.lectures.models import Lecture, RecurringSchedule, Weekday
from apps.lectures.times import local_date, local_time
from apps.notifications.audience import class_students, send_to_students, without
from apps.notifications.services import notify


def _when(lecture: Lecture) -> str:
    """Example: Mon 19 Oct 2026 at 4:00 PM PKT (the recipient's zone)."""
    return f"{local_date(lecture.starts_at)} at {local_time(lecture.starts_at)}"


def _students(lecture: Lecture):
    return class_students(
        lecture.batch_id, lecture.subjects.values_list("pk", flat=True)
    )


def _urls() -> dict[str, str]:
    return {
        "student_url": reverse("student:lecture_list"),
        "guardian_url": reverse("guardian:lecture_schedule"),
    }


def _teachers(
    event: str, text: Any, actor: Any, current: Any, url: str, old: Any = None
):
    """The lecture's teacher (its page), and a teacher it moved away from
    (their list: the lecture is no longer theirs)."""
    notify(without(actor, [current.user]), event, text, url)
    if old is not None and old.pk != current.pk:
        notify(without(actor, [old.user]), event, text, reverse("teacher:lecture_list"))


def lecture_saved(
    lecture: Lecture, *, created: bool, actor: Any = None, old_teacher: Any = None
) -> None:
    """A single lecture made, or changed in its time, length, teacher or link."""
    if created:

        def text(user: Any) -> str:
            return f"New lecture: {lecture.title}, {_when(lecture)}."
    else:

        def text(user: Any) -> str:
            return f"Lecture changed: {lecture.title} is now {_when(lecture)}."

    send_to_students(
        "lecture_changed", _students(lecture), text, **_urls(), actor=actor
    )
    url = reverse("teacher:lecture_detail", kwargs={"pk": lecture.pk})
    _teachers("lecture_changed", text, actor, lecture.teacher, url, old_teacher)


def lecture_cancelled(lecture: Lecture, *, actor: Any = None) -> None:
    def text(user: Any) -> str:
        return f"Cancelled: {lecture.title}, {_when(lecture)}."

    send_to_students(
        "lecture_cancelled", _students(lecture), text, **_urls(), actor=actor
    )
    url = reverse("teacher:lecture_detail", kwargs={"pk": lecture.pk})
    _teachers("lecture_cancelled", text, actor, lecture.teacher, url)


def lecture_started(lecture: Lecture) -> None:
    """SPEC 7: to the enrolled students only."""
    send_to_students(
        "lecture_started",
        _students(lecture),
        f"{lecture.title} has started. You can join now.",
        student_url=reverse("student:lecture_list"),
    )


def lecture_soon(lecture: Lecture) -> None:
    """SPEC 7 "starts in 15 minutes": the enrolled students and the teacher."""

    def text(user: Any) -> str:
        return f"{lecture.title} starts soon, at {local_time(lecture.starts_at)}."

    send_to_students(
        "lecture_soon",
        _students(lecture),
        text,
        student_url=reverse("student:lecture_list"),
    )
    url = reverse("teacher:lecture_detail", kwargs={"pk": lecture.pk})
    notify([lecture.teacher.user], "lecture_soon", text, url)


def _plan(schedule: RecurringSchedule) -> str:
    """Example: Mon, Wed, Fri at 4:00 PM PKT (the schedule's own zone: it is
    wall-clock time there)."""
    days = ", ".join(Weekday(day).label for day in sorted(schedule.weekdays))
    start = datetime.combine(
        schedule.start_date, schedule.start_time, tzinfo=ZoneInfo(schedule.time_zone)
    )
    return f"{days} at {date_format(start, 'g:i A T')}"


def _schedule_students(schedule: RecurringSchedule):
    return class_students(
        schedule.batch_id, schedule.subjects.values_list("pk", flat=True)
    )


def schedule_saved(
    schedule: RecurringSchedule,
    *,
    created: bool,
    actor: Any = None,
    old_teacher: Any = None,
) -> None:
    """One notification per schedule save or edit (owner decision)."""
    if created:
        text = f"New weekly schedule: {schedule.title}, {_plan(schedule)}."
    else:
        text = f"Weekly schedule changed: {schedule.title}, now {_plan(schedule)}."
    students = _schedule_students(schedule)
    send_to_students("schedule_changed", students, text, **_urls(), actor=actor)
    url = reverse("teacher:lecture_schedule_list")
    _teachers("schedule_changed", text, actor, schedule.teacher, url, old_teacher)


def schedule_stopped(
    schedule: RecurringSchedule, *, cancelled: int, actor: Any = None
) -> None:
    lectures = "lecture is" if cancelled == 1 else "lectures are"
    text = (
        f"Weekly schedule stopped: {schedule.title}. "
        f"{cancelled} upcoming {lectures} cancelled."
    )
    students = _schedule_students(schedule)
    send_to_students("lecture_cancelled", students, text, **_urls(), actor=actor)
    url = reverse("teacher:lecture_schedule_list")
    _teachers("lecture_cancelled", text, actor, schedule.teacher, url)
