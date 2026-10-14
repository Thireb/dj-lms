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
    # (2 + 1 + 0.5) / 6 = 58.333...%
    assert summary.percent == Decimal("58.3")
    assert percent_text(summary.percent) == "58.3%"


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
