"""Tenant isolation and for_user scopes for people profiles (roadmap 2.1)."""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from apps.core.tenancy import clear_current_institute, tenant_context
from apps.people.models import GuardianProfile, StudentProfile, TeacherProfile

from tests.conftest import FakeUser
from tests.people.conftest import account, guardian, student, teacher

PROFILE_MODELS = [StudentProfile, TeacherProfile, GuardianProfile]


@pytest.fixture
def people(institute_a, institute_b) -> dict:
    return {
        "student_a": student(institute_a, "s1-a@example.com"),
        "student_a2": student(institute_a, "s2-a@example.com"),
        "student_b": student(institute_b, "s1-b@example.com"),
        "teacher_a": teacher(institute_a, "t1-a@example.com"),
        "teacher_a2": teacher(institute_a, "t2-a@example.com"),
        "teacher_b": teacher(institute_b, "t1-b@example.com"),
        "guardian_a": guardian(institute_a, "g1-a@example.com"),
        "guardian_a2": guardian(institute_a, "g2-a@example.com"),
        "guardian_b": guardian(institute_b, "g1-b@example.com"),
    }


def _visible(model, user) -> set:
    return set(model.objects.for_user(user))


@pytest.mark.django_db
@pytest.mark.parametrize("model", PROFILE_MODELS)
def test_no_tenant_context_returns_nothing(people, model) -> None:
    clear_current_institute()
    assert list(model.objects.all()) == []


@pytest.mark.django_db
@pytest.mark.parametrize("model", PROFILE_MODELS)
def test_tenant_context_returns_only_that_institute(people, institute_a, model) -> None:
    with tenant_context(institute_a):
        rows = list(model.objects.all())

    assert rows
    assert {row.institute_id for row in rows} == {institute_a.pk}


@pytest.mark.django_db
@pytest.mark.parametrize("model", PROFILE_MODELS)
def test_anonymous_sees_nothing(people, anonymous_user, model) -> None:
    assert _visible(model, anonymous_user) == set()


@pytest.mark.django_db
@pytest.mark.parametrize("model", PROFILE_MODELS)
def test_user_without_institute_sees_nothing(people, model) -> None:
    assert _visible(model, FakeUser(role=Role.INSTITUTE_ADMIN)) == set()


@pytest.mark.django_db
@pytest.mark.parametrize("role", [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN])
def test_admins_see_own_institute_only(people, institute_a, role) -> None:
    user = account(institute_a, "admin-a@example.com", role)

    assert _visible(StudentProfile, user) == {
        people["student_a"],
        people["student_a2"],
    }
    assert _visible(TeacherProfile, user) == {
        people["teacher_a"],
        people["teacher_a2"],
    }
    assert _visible(GuardianProfile, user) == {
        people["guardian_a"],
        people["guardian_a2"],
    }


@pytest.mark.django_db
def test_super_admin_sees_every_institute(people) -> None:
    user = account(None, "super@example.com", Role.SUPER_ADMIN)

    assert len(_visible(StudentProfile, user)) == 3
    assert len(_visible(TeacherProfile, user)) == 3
    assert len(_visible(GuardianProfile, user)) == 3


@pytest.mark.django_db
def test_student_sees_only_own_profile(people) -> None:
    user = people["student_a"].user

    assert _visible(StudentProfile, user) == {people["student_a"]}
    assert _visible(TeacherProfile, user) == set()
    assert _visible(GuardianProfile, user) == set()


@pytest.mark.django_db
def test_teacher_cannot_see_another_teacher(people) -> None:
    user = people["teacher_a"].user

    assert _visible(TeacherProfile, user) == {people["teacher_a"]}


@pytest.mark.django_db
def test_teacher_sees_no_students_before_batches_exist(people) -> None:
    # Teachers reach students through their batches (roadmap 2.3).
    user = people["teacher_a"].user

    assert _visible(StudentProfile, user) == set()
    assert _visible(GuardianProfile, user) == set()


@pytest.mark.django_db
def test_guardian_sees_only_own_profile(people) -> None:
    user = people["guardian_a"].user

    assert _visible(GuardianProfile, user) == {people["guardian_a"]}
    assert _visible(TeacherProfile, user) == set()


@pytest.mark.django_db
def test_guardian_cannot_see_unlinked_student(people) -> None:
    # Guardians reach students only through links (roadmap 2.2).
    user = people["guardian_a"].user

    assert _visible(StudentProfile, user) == set()


@pytest.mark.django_db
def test_own_profile_scope_stays_in_own_institute(people, institute_b) -> None:
    # A student user moved to institute B must not keep seeing the A profile.
    user = people["student_a"].user
    user.institute = institute_b

    assert _visible(StudentProfile, user) == set()
