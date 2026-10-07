"""Helpers for people tests. Fake names and numbers only."""

from __future__ import annotations

from apps.accounts.models import User
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.institutes.models import Institute
from apps.people.models import GuardianProfile, StudentProfile, TeacherProfile
from apps.people.services import (
    create_guardian_profile,
    create_student_profile,
    create_teacher_profile,
)

from tests.conftest import make_user


def student(institute: Institute, email: str) -> StudentProfile:
    user = make_user(email=email, role=Role.STUDENT, institute=institute)
    with tenant_context(institute):
        return create_student_profile(user, guardian_phone="0300-0000000")


def teacher(institute: Institute, email: str) -> TeacherProfile:
    user = make_user(email=email, role=Role.TEACHER, institute=institute)
    with tenant_context(institute):
        return create_teacher_profile(user)


def guardian(institute: Institute, email: str) -> GuardianProfile:
    user = make_user(email=email, role=Role.GUARDIAN, institute=institute)
    with tenant_context(institute):
        return create_guardian_profile(user)


def account(institute: Institute | None, email: str, role: str) -> User:
    return make_user(email=email, role=role, institute=institute)
