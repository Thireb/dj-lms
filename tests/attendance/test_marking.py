"""Roadmap 4.1: the roster, saving marks and Present / Total (SPEC 6.3)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from apps.academics.models import StudentBatchSubject
from apps.attendance.models import Attendance
from apps.attendance.services import can_mark, lecture_counts, roster
from apps.core.tenancy import tenant_context
from apps.lectures.models import Lecture, LectureStatus
from django.core.exceptions import ValidationError
from django.utils import timezone

from tests.attendance.conftest import finished, mark, marks_of
from tests.people.conftest import student
from tests.school import link_student


def _roster(lecture) -> list[tuple[int, str]]:
    with tenant_context(lecture.institute):
        return [(entry.student.pk, entry.status) for entry in roster(lecture)]


def _counts(*lectures):
    with tenant_context(lectures[0].institute):
        fresh = list(
            Lecture.objects.filter(pk__in=[x.pk for x in lectures]).prefetch_related(
                "subjects"
            )
        )
        return lecture_counts(fresh)


# Who is expected


@pytest.mark.django_db
def test_roster_is_the_batch_and_subject_enrolments(old_school) -> None:
    school = old_school
    lecture = finished(school, subjects=[school.math])
    # student_2 is in Evening; student_new has no batch.
    assert _roster(lecture) == [(school.student_1.pk, "")]


@pytest.mark.django_db
def test_roster_needs_one_of_the_lecture_subjects(old_school) -> None:
    school = old_school
    other = student(school.morning.institute, "s4-a@example.com")
    link_student(other, {school.morning: [school.physics]})
    # unscoped: test set-up outside a tenant context.
    StudentBatchSubject.unscoped.filter(student=other).update(
        created_at=timezone.now() - timedelta(days=60)
    )
    math_only = finished(school, subjects=[school.math])
    assert [pk for pk, _ in _roster(math_only)] == [school.student_1.pk]


@pytest.mark.django_db
def test_student_enrolled_after_the_lecture_is_not_expected(school) -> None:
    """The fixture's enrolments are new: a lecture that ended before them
    has no roster."""
    assert _roster(finished(school, days_ago=2)) == []


@pytest.mark.django_db
def test_mark_stays_after_the_enrolment_is_removed(old_school) -> None:
    school = old_school
    lecture = finished(school)
    mark(lecture, {school.student_1: "late"})
    link_student(school.student_1, {school.evening: [school.physics]})
    assert _roster(lecture) == [(school.student_1.pk, "late")]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("status", "allowed"),
    [
        (LectureStatus.FINISHED, True),
        (LectureStatus.SCHEDULED, False),
        (LectureStatus.LIVE, False),
        (LectureStatus.NOT_HELD, False),
        (LectureStatus.CANCELLED, False),
    ],
)
def test_only_a_finished_lecture_takes_marks(old_school, status, allowed) -> None:
    lecture = finished(old_school)
    lecture.status = status
    assert can_mark(lecture) is allowed


# Saving


@pytest.mark.django_db
def test_save_creates_then_updates(old_school, institute_a) -> None:
    school = old_school
    lecture = finished(school)
    teacher = school.teacher_1.user
    assert mark(lecture, {school.student_1: "absent"}, teacher) == 1
    assert marks_of(lecture) == {school.student_1.pk: "absent"}
    assert mark(lecture, {school.student_1: "absent"}, teacher) == 0
    assert mark(lecture, {school.student_1: "partial"}, teacher) == 1
    assert marks_of(lecture) == {school.student_1.pk: "partial"}
    row = Attendance.unscoped.get(lecture=lecture)
    assert row.marked_by == teacher
    assert row.institute == institute_a


@pytest.mark.django_db
def test_save_refuses_a_lecture_that_is_not_finished(old_school) -> None:
    school = old_school
    lecture = finished(school)
    Lecture.unscoped.filter(pk=lecture.pk).update(status=LectureStatus.NOT_HELD)
    with pytest.raises(ValidationError, match="only for a finished lecture"):
        mark(lecture, {school.student_1: "present"})
    assert marks_of(lecture) == {}


@pytest.mark.django_db
def test_save_refuses_a_student_not_on_the_roster(old_school) -> None:
    school = old_school
    lecture = finished(school)
    with pytest.raises(ValidationError, match="not in this lecture"):
        mark(lecture, {school.student_1: "present", school.student_2: "present"})
    assert marks_of(lecture) == {}


@pytest.mark.django_db
def test_save_refuses_an_unknown_status(old_school) -> None:
    lecture = finished(old_school)
    with pytest.raises(ValidationError, match="Choose Present"):
        mark(lecture, {old_school.student_1: "excused"})
    assert marks_of(lecture) == {}


# Present / Total


@pytest.mark.django_db
def test_counts_attended_out_of_expected(old_school) -> None:
    school = old_school
    second = student(school.morning.institute, "s5-a@example.com")
    third = student(school.morning.institute, "s6-a@example.com")
    for profile in (second, third):
        link_student(profile, {school.morning: [school.math]})
    StudentBatchSubject.unscoped.update(created_at=timezone.now() - timedelta(days=9))
    lecture = finished(school)
    empty = finished(school, title="Not taken yet", days_ago=3)
    mark(lecture, {school.student_1: "partial", second: "absent"})
    counts = _counts(lecture, empty)
    assert counts[lecture.pk].attended == 1  # partial counts as attended
    assert counts[lecture.pk].marked == 2
    assert counts[lecture.pk].total == 3  # third is expected, not marked
    assert counts[empty.pk].marked == 0
    assert counts[empty.pk].total == 3


@pytest.mark.django_db
def test_counts_late_and_present_attend(old_school) -> None:
    school = old_school
    second = student(school.morning.institute, "s7-a@example.com")
    link_student(second, {school.morning: [school.math]})
    StudentBatchSubject.unscoped.update(created_at=timezone.now() - timedelta(days=9))
    lecture = finished(school)
    mark(lecture, {school.student_1: "late", second: "present"})
    assert _counts(lecture)[lecture.pk].attended == 2


@pytest.mark.django_db
def test_counts_of_no_lectures_is_empty(old_school) -> None:
    assert lecture_counts([]) == {}
