"""Attendance rows: creation, tenant isolation and ``for_user`` scopes
(AGENTS.md section 7)."""

from __future__ import annotations

import pytest
from apps.attendance.models import Attendance, AttendanceSource, AttendanceStatus
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from tests.attendance.conftest import finished, mark
from tests.conftest import make_user
from tests.lectures.conftest import add_lecture


def _row(lecture, student, status=AttendanceStatus.PRESENT) -> Attendance:
    with tenant_context(lecture.institute):
        return Attendance.objects.create(
            institute=lecture.institute,
            lecture=lecture,
            student=student,
            status=status,
        )


@pytest.mark.django_db
def test_create_defaults_to_manual(old_school) -> None:
    row = _row(finished(old_school), old_school.student_1)
    assert row.source == AttendanceSource.MANUAL
    assert row.marked_at is not None


@pytest.mark.django_db
def test_one_row_per_lecture_and_student(old_school) -> None:
    lecture = finished(old_school)
    _row(lecture, old_school.student_1)
    with pytest.raises(IntegrityError), transaction.atomic():
        _row(lecture, old_school.student_1, AttendanceStatus.ABSENT)


@pytest.mark.django_db
def test_student_of_another_institute_is_refused(old_school) -> None:
    with pytest.raises(ValidationError):
        _row(finished(old_school), old_school.student_b)


@pytest.mark.django_db
def test_no_context_and_anonymous_see_nothing(old_school, anonymous_user) -> None:
    _row(finished(old_school), old_school.student_1)
    assert not Attendance.objects.exists()
    assert not Attendance.objects.for_user(anonymous_user).exists()
    assert not Attendance.objects.for_user(None).exists()


@pytest.mark.django_db
def test_admin_sees_only_own_institute(old_school, institute_a, institute_b) -> None:
    _row(finished(old_school), old_school.student_1)
    admin_a = make_user(
        email="a@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_a
    )
    admin_b = make_user(
        email="b@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_b
    )
    assert Attendance.objects.for_user(admin_a).count() == 1
    assert not Attendance.objects.for_user(admin_b).exists()


@pytest.mark.django_db
def test_teacher_sees_rows_of_own_lectures_only(old_school) -> None:
    school = old_school
    own = finished(school)
    other = finished(
        school,
        title="Evening physics",
        teacher=school.teacher_2,
        batch=school.evening,
        subjects=[school.physics],
    )
    mark(own, {school.student_1: "present"})
    mark(other, {school.student_2: "absent"})
    mine = Attendance.objects.for_user(school.teacher_1.user)
    theirs = Attendance.objects.for_user(school.teacher_2.user)
    assert list(mine.values_list("lecture_id", flat=True)) == [own.pk]
    assert list(theirs.values_list("lecture_id", flat=True)) == [other.pk]


@pytest.mark.django_db
def test_student_and_guardian_see_own_child_only(old_school) -> None:
    school = old_school
    lecture = finished(school, subjects=[school.math])
    evening = finished(
        school,
        title="Evening physics",
        teacher=school.teacher_2,
        batch=school.evening,
        subjects=[school.physics],
    )
    mark(lecture, {school.student_1: "late"})
    mark(evening, {school.student_2: "absent"})
    for user in (school.student_1.user, school.guardian_1.user):
        rows = Attendance.objects.for_user(user)
        assert list(rows.values_list("student_id", flat=True)) == [
            school.student_1.pk
        ], user.email
    assert not Attendance.objects.for_user(school.teacher_idle.user).exists()


@pytest.mark.django_db
def test_sub_admin_sees_the_institute(old_school, institute_a) -> None:
    _row(finished(old_school), old_school.student_1)
    sub = make_user(email="sub@example.com", role=Role.SUB_ADMIN, institute=institute_a)
    assert Attendance.objects.for_user(sub).count() == 1


@pytest.mark.django_db
def test_lecture_of_another_institute_is_refused(old_school) -> None:
    lecture = add_lecture(old_school)
    with tenant_context(lecture.institute), pytest.raises(ValidationError):
        Attendance(
            institute=old_school.student_b.institute,
            lecture=lecture,
            student=old_school.student_b,
            status=AttendanceStatus.PRESENT,
        ).save()
