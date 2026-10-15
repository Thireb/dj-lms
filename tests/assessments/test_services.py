"""Publish, submit and grade rules (roadmap 5.1, SPEC 4.16 and 6.8), with
real numbers."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.academics.models import StudentBatchSubject
from apps.assessments.models import SubmissionStatus
from apps.assessments.services import (
    CLOSED_MESSAGE,
    answers_to_grade,
    assignment_counts,
    marks_text,
    student_assignments,
    submission_rows,
    update_assignment,
)
from apps.core.tenancy import tenant_context
from apps.people.models import ProfileStatus, StudentProfile
from django.core.exceptions import ValidationError
from django.utils import timezone

from tests.assessments.conftest import (
    add_assignment,
    answer,
    assignment_details,
    close,
    grade,
    in_days,
)
from tests.attendance.conftest import backdate_enrolments
from tests.people.conftest import student
from tests.school import link_student, link_teacher


def _errors(error: ValidationError) -> dict:
    return error.value.message_dict


def _update(assignment, school, **fields):
    with tenant_context(assignment.institute):
        return update_assignment(assignment, assignment_details(school, **fields))


def _statuses(assignment) -> dict[str, str]:
    with tenant_context(assignment.institute):
        return {
            str(row.student.student_code): row.status
            for row in submission_rows(assignment)
        }


# Publish


@pytest.mark.django_db
def test_teacher_must_teach_the_batch_and_subject(school) -> None:
    with pytest.raises(ValidationError) as error:
        add_assignment(school, subject=school.physics)
    assert _errors(error) == {"subject": ["The teacher does not teach this subject."]}


@pytest.mark.django_db
def test_inactive_batch_is_refused(school) -> None:
    school.morning.is_active = False
    with tenant_context(school.morning.institute):
        school.morning.save()
    with pytest.raises(ValidationError) as error:
        add_assignment(school)
    assert _errors(error) == {"subject": ["This batch or subject is inactive."]}


@pytest.mark.django_db
def test_due_time_must_be_in_the_future(school) -> None:
    with pytest.raises(ValidationError) as error:
        add_assignment(school, due_at=in_days(-0.01))
    assert _errors(error) == {"due_at": ["Choose a due time in the future."]}


@pytest.mark.django_db
def test_other_institute_rows_are_refused(school) -> None:
    with pytest.raises(ValidationError) as error:
        add_assignment(school, batch=school.batch_b)
    assert _errors(error) == {"batch": ["Must belong to this institute."]}


@pytest.mark.django_db
def test_edit_keeps_a_past_due_time_that_did_not_change(school) -> None:
    assignment = close(add_assignment(school))
    saved = _update(assignment, school, title="Renamed", due_at=assignment.due_at)
    assert saved.title == "Renamed"
    with pytest.raises(ValidationError) as error:
        _update(assignment, school, due_at=in_days(-2))
    assert "due_at" in _errors(error)


@pytest.mark.django_db
def test_edit_cannot_drop_total_below_a_grade(school) -> None:
    assignment = add_assignment(school)
    grade(answer(assignment, school.student_1), "7.5")
    with pytest.raises(ValidationError) as error:
        _update(assignment, school, total_marks=7)
    assert _errors(error) == {
        "total_marks": ["A student already has 7.5 marks. Total marks cannot be less."]
    }
    assert _update(assignment, school, total_marks=8).total_marks == 8


@pytest.mark.django_db
def test_edit_keeps_the_class_after_an_answer(school) -> None:
    link_teacher(school.teacher_1, {school.morning: [school.math, school.physics]})
    assignment = add_assignment(school)
    assert _update(assignment, school, subject=school.physics).subject == school.physics
    answer(assignment, school.student_1)
    with pytest.raises(ValidationError) as error:
        _update(assignment, school, subject=school.math)
    assert _errors(error) == {
        "subject": ["Students have answered, so the batch and subject stay the same."]
    }


@pytest.mark.django_db
def test_edit_cannot_change_the_teacher(school) -> None:
    assignment = add_assignment(school)
    with pytest.raises(ValidationError) as error:
        _update(assignment, school, teacher=school.teacher_2)
    assert "teacher" in _errors(error)


# Statuses (SPEC 2)


@pytest.mark.django_db
def test_statuses_before_and_after_the_due_time(old_school) -> None:
    school = old_school
    second = student(school.morning.institute, "s4-a@example.com")
    third = student(school.morning.institute, "s5-a@example.com")
    link_student(second, {school.morning: [school.math]})
    link_student(third, {school.morning: [school.math]})
    backdate_enrolments()
    assignment = add_assignment(school)
    grade(answer(assignment, school.student_1), "6")
    answer(assignment, second)
    codes = (school.student_1, second, third)
    s1, s2, s3 = (str(person.student_code) for person in codes)

    assert _statuses(assignment) == {
        s1: SubmissionStatus.GRADED,
        s2: SubmissionStatus.SUBMITTED,
        s3: SubmissionStatus.PENDING,
    }
    close(assignment)
    assert _statuses(assignment) == {
        s1: SubmissionStatus.GRADED,
        s2: SubmissionStatus.SUBMITTED,
        s3: SubmissionStatus.MISSED,
    }


@pytest.mark.django_db
def test_expected_students(school) -> None:
    """Enrolled in the batch and subject before the due time, and active; or
    already answered."""
    assignment = add_assignment(school)
    late = student(school.morning.institute, "s4-a@example.com")
    left = student(school.morning.institute, "s5-a@example.com")
    link_student(late, {school.morning: [school.math]})
    link_student(left, {school.morning: [school.math]})
    answer(assignment, left)
    # unscoped: test set-up outside a tenant context.
    StudentProfile.unscoped.filter(pk=left.pk).update(status=ProfileStatus.INACTIVE)
    StudentBatchSubject.unscoped.filter(student=late).update(
        created_at=assignment.due_at + timedelta(minutes=1)
    )
    expected = set(_statuses(assignment))
    assert expected == {str(school.student_1.student_code), str(left.student_code)}


# Submit


@pytest.mark.django_db
def test_answer_can_change_until_graded(school) -> None:
    assignment = add_assignment(school)
    first = answer(assignment, school.student_1, "First try.")
    second = answer(assignment, school.student_1, "Second try.")
    assert second.pk == first.pk and second.answer == "Second try."
    grade(second, "9")
    with pytest.raises(ValidationError, match="graded and cannot change"):
        answer(assignment, school.student_1, "Third try.")


@pytest.mark.django_db
def test_no_answer_after_the_due_time(school) -> None:
    assignment = close(add_assignment(school))
    with pytest.raises(ValidationError) as error:
        answer(assignment, school.student_1)
    assert error.value.messages == [CLOSED_MESSAGE]


@pytest.mark.django_db
def test_only_expected_students_answer(school) -> None:
    assignment = add_assignment(school)
    with pytest.raises(ValidationError, match="not for this student"):
        answer(assignment, school.student_2)


@pytest.mark.django_db
def test_blank_answer_is_refused(school) -> None:
    with pytest.raises(ValidationError) as error:
        answer(add_assignment(school), school.student_1, "   ")
    assert _errors(error) == {"answer": ["Write your answer."]}


# Grade


@pytest.mark.django_db
def test_grade_from_zero_to_total(school) -> None:
    row = answer(add_assignment(school, total_marks=20), school.student_1)
    assert grade(row, "0").marks == Decimal("0")
    graded = grade(row, "17.5", "Good work.")
    assert graded.marks == Decimal("17.5")
    assert graded.feedback == "Good work."
    assert graded.graded_at is not None
    with pytest.raises(ValidationError) as error:
        grade(row, "20.5")
    assert _errors(error) == {"marks": ["Give 0 to 20 marks."]}
    with pytest.raises(ValidationError):
        grade(row, "-1")


def test_marks_text() -> None:
    assert marks_text(Decimal("7.5"), 10) == "7.5 / 10"
    assert marks_text(Decimal("7.0"), 10) == "7 / 10"
    assert marks_text(None, 10) == "-"


# Counts and lists


@pytest.mark.django_db
def test_counts_with_real_numbers(school) -> None:
    second = student(school.morning.institute, "s4-a@example.com")
    third = student(school.morning.institute, "s5-a@example.com")
    link_student(second, {school.morning: [school.math]})
    link_student(third, {school.morning: [school.physics]})  # not Math
    assignment = add_assignment(school)
    empty = add_assignment(school, title="Nobody answered")
    grade(answer(assignment, school.student_1), "8")
    answer(assignment, second)

    with tenant_context(assignment.institute):
        counts = assignment_counts([assignment, empty])
        to_grade = answers_to_grade(school.teacher_1.user)
    assert (counts[assignment.pk].submitted, counts[assignment.pk].total) == (2, 2)
    assert counts[assignment.pk].graded == 1
    assert counts[assignment.pk].to_grade == 1
    assert (counts[empty.pk].submitted, counts[empty.pk].total) == (0, 2)
    assert to_grade == 1


@pytest.mark.django_db
def test_student_list_order_and_filters(old_school) -> None:
    school = old_school
    link_teacher(school.teacher_1, {school.morning: [school.math, school.physics]})
    later = add_assignment(school, title="Later", due_at=in_days(5))
    sooner = add_assignment(school, title="Sooner", due_at=in_days(1))
    old = close(add_assignment(school, title="Old"), days_ago=3)
    older = close(add_assignment(school, title="Older"), days_ago=6)
    physics = add_assignment(school, title="Optics", subject=school.physics)
    answer(sooner, school.student_1)

    def titles(**filters) -> list[str]:
        with tenant_context(school.morning.institute):
            rows = student_assignments(school.student_1, **filters)
        return [row.assignment.title for row in rows]

    assert titles() == ["Sooner", "Optics", "Later", "Old", "Older"]
    assert titles(status=SubmissionStatus.MISSED) == ["Old", "Older"]
    assert titles(status=SubmissionStatus.SUBMITTED) == ["Sooner"]
    assert titles(subject_id=school.physics.pk) == ["Optics"]
    assert {later.pk, old.pk, older.pk, physics.pk}  # all made


@pytest.mark.django_db
def test_student_does_not_get_assignments_due_before_enrolment(school) -> None:
    assignment = add_assignment(school)
    newcomer = student(school.morning.institute, "s4-a@example.com")
    link_student(newcomer, {school.morning: [school.math]})
    # unscoped: test set-up outside a tenant context.
    StudentBatchSubject.unscoped.filter(student=newcomer).update(
        created_at=timezone.now() + timedelta(days=4)
    )
    with tenant_context(school.morning.institute):
        assert student_assignments(newcomer) == []
        assert [row.assignment for row in student_assignments(school.student_1)] == [
            assignment
        ]
