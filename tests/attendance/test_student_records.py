"""Roadmap 4.2 and 4.3 services: a student's records and the attendance %
(SPEC 6.3), with real numbers."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.attendance.services import Record, Summary, student_records, summarize
from apps.attendance.ui import percent_text
from apps.core.tenancy import tenant_context
from apps.lectures.models import Lecture, LectureStatus
from django.utils import timezone

from tests.attendance.conftest import finished, mark
from tests.school import link_student, link_teacher


def _records(student, **filters) -> list[tuple[str, str]]:
    with tenant_context(student.institute):
        return [
            (record.lecture.title, record.status)
            for record in student_records(student, **filters)
        ]


# The %


def test_percent_counts_late_and_half_of_partial() -> None:
    summary = Summary(present=2, late=1, partial=1, absent=1, not_marked=1)
    assert summary.total == 6
    assert summary.marked == 5
    # Not marked is left out (owner decision 2026-10-14): (2 + 1 + 0.5) / 5
    assert summary.percent == Decimal("70.0")
    assert percent_text(summary.percent) == "70%"


# Owner decision 2026-10-14 (audit P4-5): only marked classes count.


def test_ten_classes_one_not_marked() -> None:
    summary = Summary(present=4, late=2, partial=2, absent=1, not_marked=1)
    assert (summary.total, summary.marked) == (10, 9)
    # (4 + 2 + 0.5 x 2) / 9 = 7 / 9 = 77.77...%
    assert summary.percent == Decimal("77.8")


def test_nothing_marked_has_no_percent() -> None:
    summary = Summary(not_marked=10)
    assert summary.total == 10
    assert summary.percent is None


def test_waiting_classes_do_not_lower_the_percent() -> None:
    assert Summary(present=1, not_marked=2).percent == Decimal("100.0")
    assert Summary(partial=1).percent == Decimal("50.0")
    assert Summary(present=1, absent=1).percent == Decimal("50.0")


def test_percent_rounds_half_up() -> None:
    # 1 partial in 8: 0.5 / 8 = 6.25%
    assert Summary(partial=1, absent=7).percent == Decimal("6.3")


def test_percent_of_all_present_and_of_nothing() -> None:
    assert percent_text(Summary(present=3).percent) == "100%"
    assert percent_text(Summary(absent=4).percent) == "0%"
    assert Summary().percent is None
    assert percent_text(None) == "-"


def test_summarize_counts_each_status() -> None:
    statuses = ["present", "late", "late", "partial", "absent", "", ""]
    summary = summarize([Record(None, status) for status in statuses])
    assert summary == Summary(present=1, late=2, partial=1, absent=1, not_marked=2)


# Which lectures count


@pytest.mark.django_db
def test_records_are_finished_expected_lectures_newest_first(old_school) -> None:
    school = old_school
    older = finished(school, title="Older", days_ago=3)
    newer = finished(school, title="Newer", days_ago=1)
    mark(older, {school.student_1: "absent"})
    not_held = finished(school, title="Not held", days_ago=2)
    # unscoped: test set-up outside a tenant context.
    Lecture.unscoped.filter(pk=not_held.pk).update(status=LectureStatus.NOT_HELD)
    finished(
        school,
        title="Evening class",
        teacher=school.teacher_2,
        batch=school.evening,
        subjects=[school.physics],
    )
    assert newer
    assert _records(school.student_1) == [("Newer", ""), ("Older", "absent")]
    assert _records(school.student_2) == [("Evening class", "")]


@pytest.mark.django_db
def test_lecture_before_the_enrolment_does_not_count(school) -> None:
    """The fixture's enrolments are new; a lecture 3 days ago ended first."""
    finished(school, title="Before", days_ago=3)
    assert _records(school.student_1) == []


@pytest.mark.django_db
def test_marked_lecture_stays_after_leaving_the_batch(old_school) -> None:
    school = old_school
    lecture = finished(school, title="Marked")
    finished(school, title="Unmarked", days_ago=2)
    mark(lecture, {school.student_1: "present"})
    link_student(school.student_1, {school.evening: [school.physics]})
    assert _records(school.student_1) == [("Marked", "present")]


@pytest.mark.django_db
def test_records_filter_by_subject_and_dates(old_school) -> None:
    school = old_school
    link_teacher(school.teacher_1, {school.morning: [school.math, school.physics]})
    finished(school, title="Math one", days_ago=10)
    finished(school, title="Physics one", subjects=[school.physics], days_ago=5)
    finished(school, title="Math two", days_ago=1)
    assert [t for t, _ in _records(school.student_1, subject_id=school.math.pk)] == [
        "Math two",
        "Math one",
    ]
    today = timezone.localdate()
    assert [
        t
        for t, _ in _records(
            school.student_1,
            date_from=today - timedelta(days=6),
            date_to=today - timedelta(days=2),
        )
    ] == ["Physics one"]


# Month and subject summaries (roadmap 4.3)


def _lecture(starts_at, *subjects):
    """An unsaved lecture with its subjects as if prefetched."""
    _lecture.count = getattr(_lecture, "count", 0) + 1
    lecture = Lecture(pk=_lecture.count, starts_at=starts_at, duration_minutes=60)
    lecture._prefetched_objects_cache = {"subjects": list(subjects)}
    return lecture


def test_by_month_groups_newest_first_in_the_viewer_zone(settings) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from apps.academics.models import Subject
    from apps.attendance.services import by_month
    from django.utils import timezone as dj_timezone

    math = Subject(pk=1, name="Math")
    utc = ZoneInfo("UTC")
    records = [
        # 30 Sep 21:00 UTC is 1 Oct 02:00 in Karachi.
        Record(_lecture(datetime(2026, 9, 30, 21, tzinfo=utc), math), "present"),
        Record(_lecture(datetime(2026, 9, 10, 9, tzinfo=utc), math), "absent"),
        Record(_lecture(datetime(2026, 10, 5, 9, tzinfo=utc), math), "partial"),
    ]
    with dj_timezone.override(ZoneInfo("Asia/Karachi")):
        months = by_month(records)
    assert [(m.label, m.summary.total) for m in months] == [
        ("October 2026", 2),
        ("September 2026", 1),
    ]
    # October: 1 present + 0.5 partial out of 2 = 75%
    assert months[0].summary.percent == Decimal("75.0")
    assert months[1].summary.percent == Decimal("0.0")


def test_by_subject_counts_own_subjects_of_a_shared_lecture() -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from apps.academics.models import Subject
    from apps.attendance.services import by_subject

    math, physics, art = (
        Subject(pk=1, name="Math"),
        Subject(pk=2, name="Physics"),
        Subject(pk=3, name="Art"),
    )
    when = datetime(2026, 10, 5, 9, tzinfo=ZoneInfo("UTC"))
    records = [
        Record(_lecture(when, math, physics), "late"),  # takes both
        Record(_lecture(when, math, art), "absent"),  # takes Math only
        Record(_lecture(when, art), "present"),  # left Art: still counted
    ]
    subjects = by_subject(records, {math.pk, physics.pk})
    assert [(s.label, s.summary.total) for s in subjects] == [
        ("Art", 1),
        ("Math", 2),
        ("Physics", 1),
    ]
    assert subjects[1].summary.percent == Decimal("50.0")


@pytest.mark.django_db
def test_summaries_for_many_students_match_the_records(old_school) -> None:
    from apps.attendance.services import student_summaries

    school = old_school
    one = finished(school, title="One", days_ago=2)
    finished(school, title="Two", days_ago=1)
    evening = finished(
        school,
        title="Evening",
        teacher=school.teacher_2,
        batch=school.evening,
        subjects=[school.physics],
    )
    mark(one, {school.student_1: "late"})
    mark(evening, {school.student_2: "partial"})
    with tenant_context(school.morning.institute):
        summaries = student_summaries(
            [school.student_1, school.student_2, school.student_new]
        )
    assert summaries[school.student_1.pk] == Summary(late=1, not_marked=1)
    assert summaries[school.student_2.pk] == Summary(partial=1)
    assert summaries[school.student_new.pk] == Summary()
