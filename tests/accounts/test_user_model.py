"""User role properties and institute validation."""

from __future__ import annotations

import pytest
from apps.accounts.models import User
from apps.core.roles import Role
from apps.institutes.models import Institute
from django.core.exceptions import ValidationError


@pytest.mark.parametrize(
    ("role", "true_property"),
    [
        (Role.SUPER_ADMIN, "is_super_admin"),
        (Role.INSTITUTE_ADMIN, "is_institute_admin"),
        (Role.SUB_ADMIN, "is_sub_admin"),
        (Role.TEACHER, "is_teacher"),
        (Role.STUDENT, "is_student"),
        (Role.GUARDIAN, "is_guardian"),
    ],
)
@pytest.mark.django_db
def test_role_sets_exactly_one_is_property(
    role: str,
    true_property: str,
    institute_a: Institute,
) -> None:
    institute = None if role == Role.SUPER_ADMIN else institute_a
    user = User(
        email=f"{role}@example.com",
        role=role,
        institute=institute,
    )
    props = (
        "is_super_admin",
        "is_institute_admin",
        "is_sub_admin",
        "is_teacher",
        "is_student",
        "is_guardian",
    )
    for name in props:
        expected = name == true_property
        assert getattr(user, name) is expected, name


@pytest.mark.django_db
def test_super_admin_with_institute_fails_validation(institute_a: Institute) -> None:
    user = User(
        email="bad-super@example.com",
        role=Role.SUPER_ADMIN,
        institute=institute_a,
    )
    with pytest.raises(ValidationError) as exc_info:
        user.full_clean()
    assert "institute" in exc_info.value.error_dict


@pytest.mark.parametrize(
    "role",
    [
        Role.INSTITUTE_ADMIN,
        Role.SUB_ADMIN,
        Role.TEACHER,
        Role.STUDENT,
        Role.GUARDIAN,
    ],
)
@pytest.mark.django_db
def test_non_super_admin_without_institute_fails_validation(role: str) -> None:
    user = User(email=f"no-inst-{role}@example.com", role=role, institute=None)
    with pytest.raises(ValidationError) as exc_info:
        user.full_clean()
    assert "institute" in exc_info.value.error_dict


@pytest.mark.parametrize(
    "role",
    [
        Role.INSTITUTE_ADMIN,
        Role.SUB_ADMIN,
        Role.TEACHER,
        Role.STUDENT,
        Role.GUARDIAN,
    ],
)
@pytest.mark.django_db
def test_non_super_admin_with_institute_saves(
    role: str, institute_a: Institute
) -> None:
    user = User.objects.create_user(
        email=f"ok-{role}@example.com",
        password="pass",
        role=role,
        institute=institute_a,
    )
    user.refresh_from_db()
    assert user.institute_id == institute_a.pk


@pytest.mark.parametrize(
    "role",
    [
        Role.INSTITUTE_ADMIN,
        Role.TEACHER,
    ],
)
@pytest.mark.django_db
def test_non_super_admin_rejects_django_admin_flags(
    role: str, institute_a: Institute
) -> None:
    user = User(
        email=f"staff-{role}@example.com",
        role=role,
        institute=institute_a,
        is_staff=True,
    )
    with pytest.raises(ValidationError):
        user.full_clean()


@pytest.mark.django_db
def test_super_admin_without_institute_saves() -> None:
    user = User.objects.create_user(
        email="super@example.com",
        password="pass",
        role=Role.SUPER_ADMIN,
        institute=None,
    )
    assert user.role == Role.SUPER_ADMIN
    assert user.institute_id is None
