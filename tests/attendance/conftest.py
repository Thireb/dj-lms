"""Helpers for attendance tests. Fake names only."""

from __future__ import annotations

from datetime import timedelta

import pytest
from apps.academics.models import StudentBatchSubject
from apps.attendance.models import Attendance
from apps.attendance.services import save_marks
from apps.core.tenancy import tenant_context
from apps.lectures.models import Lecture, LectureStatus
from django.utils import timezone

from tests.lectures.conftest import add_lecture, admin_client  # noqa: F401


def backdate_enrolments(days: int = 60) -> None:
    """Enrolments made by the fixture are new; past lectures need older ones."""
    # unscoped: test set-up outside a tenant context.
    StudentBatchSubject.unscoped.update(
        created_at=timezone.now() - timedelta(days=days)
    )


def finished(school, *, days_ago: int = 1, **fields) -> Lecture:
    """A finished lecture of teacher 1 (Morning, Math by default)."""
    lecture = add_lecture(school, **fields)
    starts = timezone.now() - timedelta(days=days_ago)
    # unscoped: test set-up; the services refuse a past start.
    Lecture.unscoped.filter(pk=lecture.pk).update(
        starts_at=starts, status=LectureStatus.FINISHED
    )
    lecture.refresh_from_db()
    return lecture


def mark(lecture: Lecture, marks: dict, user=None) -> int:
    with tenant_context(lecture.institute):
        return save_marks(
            lecture, {s.pk: status for s, status in marks.items()}, marked_by=user
        )


def marks_of(lecture: Lecture) -> dict[int, str]:
    # unscoped: test assertion outside a tenant context.
    rows = Attendance.unscoped.filter(lecture=lecture)
    return dict(rows.values_list("student_id", "status"))


@pytest.fixture
def old_school(school):
    """The school with enrolments 60 days old."""
    backdate_enrolments()
    return school
