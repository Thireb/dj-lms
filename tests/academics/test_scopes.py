"""for_user scopes through batches (roadmap 2.3, ARCHITECTURE section 4)."""

from __future__ import annotations

import pytest
from apps.academics.models import (
    Batch,
    ClassLabel,
    StudentBatchSubject,
    Subject,
    TeacherBatchSubject,
)
from apps.core.roles import Role
from apps.people.models import GuardianProfile, StudentProfile, TeacherProfile

from tests.academics.conftest import link_student
from tests.people.conftest import account


def _visible(model, profile_or_user) -> list:
    user = getattr(profile_or_user, "user", profile_or_user)
    return list(model.objects.for_user(user))


def _names(rows) -> set:
    return {row.name for row in rows}


# Batches, subjects and class labels


@pytest.mark.django_db
@pytest.mark.parametrize("role", [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN])
def test_admins_see_every_list_row_in_institute(school, institute_a, role) -> None:
    user = account(institute_a, "admin-a@example.com", role)

    assert _names(_visible(Batch, user)) == {"Morning", "Evening"}
    assert _names(_visible(Subject, user)) == {"Math", "Physics"}
    assert _names(_visible(ClassLabel, user)) == {"Grade 9"}


@pytest.mark.django_db
def test_super_admin_sees_every_institute(school) -> None:
    user = account(None, "super@example.com", Role.SUPER_ADMIN)

    assert len(_visible(Batch, user)) == 3


@pytest.mark.django_db
def test_teacher_sees_own_batches_and_subjects(school) -> None:
    assert _visible(Batch, school.teacher_1) == [school.morning]
    assert _visible(Subject, school.teacher_1) == [school.math]
    assert _visible(Batch, school.teacher_idle) == []


@pytest.mark.django_db
def test_student_sees_own_batches_once(school) -> None:
    # Two subjects in Morning must not list Morning twice.
    assert _visible(Batch, school.student_1) == [school.morning]
    assert _names(_visible(Subject, school.student_1)) == {"Math", "Physics"}
    assert _visible(Batch, school.student_new) == []


@pytest.mark.django_db
def test_guardian_sees_child_batches_and_subjects(school) -> None:
    assert _visible(Batch, school.guardian_2) == [school.evening]
    assert _visible(Subject, school.guardian_2) == [school.physics]


@pytest.mark.django_db
def test_class_labels_are_admin_only(school) -> None:
    for profile in (school.teacher_1, school.student_1, school.guardian_1):
        assert _visible(ClassLabel, profile) == []


# Enrolment and teaching links


@pytest.mark.django_db
def test_teacher_sees_enrolments_of_own_batches_only(school) -> None:
    rows = _visible(StudentBatchSubject, school.teacher_1)

    assert {row.student for row in rows} == {school.student_1}
    assert len(rows) == 2


@pytest.mark.django_db
def test_student_and_guardian_see_own_enrolments(school) -> None:
    own = _visible(StudentBatchSubject, school.student_2)
    child = _visible(StudentBatchSubject, school.guardian_1)

    assert {row.student for row in own} == {school.student_2}
    assert {row.student for row in child} == {school.student_1}


@pytest.mark.django_db
def test_teacher_sees_own_teaching_links_only(school) -> None:
    rows = _visible(TeacherBatchSubject, school.teacher_1)

    assert {row.teacher for row in rows} == {school.teacher_1}


@pytest.mark.django_db
def test_student_and_guardian_see_teachers_of_their_batches(school) -> None:
    rows = _visible(TeacherBatchSubject, school.student_1)
    child = _visible(TeacherBatchSubject, school.guardian_2)

    assert [row.teacher for row in rows] == [school.teacher_1]
    assert [row.teacher for row in child] == [school.teacher_2]
    assert _visible(TeacherBatchSubject, school.student_new) == []


# Profiles reached through batches


@pytest.mark.django_db
def test_teacher_sees_students_of_own_batches_once(school) -> None:
    assert _visible(StudentProfile, school.teacher_1) == [school.student_1]
    assert _visible(StudentProfile, school.teacher_2) == [school.student_2]
    assert _visible(StudentProfile, school.teacher_idle) == []


@pytest.mark.django_db
def test_teacher_cannot_see_students_of_another_institute(school) -> None:
    assert _visible(StudentProfile, school.teacher_b) == [school.student_b]


@pytest.mark.django_db
def test_student_sees_teachers_of_own_batches(school) -> None:
    assert _visible(TeacherProfile, school.student_1) == [school.teacher_1]
    assert _visible(TeacherProfile, school.student_new) == []


@pytest.mark.django_db
def test_guardian_sees_teachers_of_child_batches(school) -> None:
    assert _visible(TeacherProfile, school.guardian_1) == [school.teacher_1]
    assert _visible(TeacherProfile, school.guardian_2) == [school.teacher_2]


@pytest.mark.django_db
def test_teacher_still_sees_only_own_teacher_profile(school) -> None:
    assert _visible(TeacherProfile, school.teacher_1) == [school.teacher_1]


@pytest.mark.django_db
def test_teacher_sees_no_guardian_profiles_yet(school) -> None:
    # Guardians of a teacher's students are for messaging (Phase 6).
    assert _visible(GuardianProfile, school.teacher_1) == []


@pytest.mark.django_db
def test_student_still_cannot_see_classmates(school) -> None:
    link_student(school.student_new, {school.morning: [school.math]})

    assert _visible(StudentProfile, school.student_1) == [school.student_1]
    assert _visible(StudentProfile, school.teacher_1) == [
        school.student_new,
        school.student_1,
    ]
