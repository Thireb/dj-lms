"""Shared pytest fixtures for tenant tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from apps.accounts.models import User
from apps.core.roles import Role
from apps.institutes.models import Institute, Plan

from tests.testapp.models import TenantProbe

# Fake test-only passwords. Never real credentials (AGENTS.md section 6).
TEST_LOGIN_PASSWORD = "fake-login-Pass-7kM"
TEST_NEW_PASSWORD = "fake-new-Pass-4nP"
TEST_ROTATED_PASSWORD = "fake-rotated-Pass-2jH"
TEST_CONFIRM_MISMATCH_PASSWORD = "fake-mismatch-Pass-9wL"
# Long enough for min_length, but too common for validate_password.
TEST_INVALID_PASSWORD_FOR_VALIDATION = "password123"
TEST_WRONG_LOGIN_PASSWORD = "fake-wrong-Pass-0xZ"
TEST_INITIAL_USER_PASSWORD = "fake-initial-Pass-8vN"


@dataclass
class FakeUser:
    """Minimal user stand-in until apps.accounts exists."""

    role: str
    institute_id: int | None = None
    institute: Institute | None = None
    timezone: str | None = None
    is_authenticated: bool = True
    allowed_menus: list[str] | None = None

    @property
    def is_super_admin(self) -> bool:
        return self.role == Role.SUPER_ADMIN

    @property
    def pk(self) -> None:
        return None


@pytest.fixture
def basic_plan(db: Any) -> Plan:
    return Plan.default_basic()


@pytest.fixture
def institute_a(db: Any, basic_plan: Plan) -> Institute:
    return Institute.objects.create(
        name="Institute A",
        timezone="Asia/Karachi",
        plan=basic_plan,
    )


@pytest.fixture
def institute_b(db: Any, basic_plan: Plan) -> Institute:
    return Institute.objects.create(
        name="Institute B",
        timezone="Europe/London",
        plan=basic_plan,
    )


@pytest.fixture
def probe_a(institute_a: Institute) -> TenantProbe:
    return TenantProbe.objects.create(institute=institute_a, label="probe-a")


@pytest.fixture
def probe_b(institute_b: Institute) -> TenantProbe:
    return TenantProbe.objects.create(institute=institute_b, label="probe-b")


@pytest.fixture
def admin_a(institute_a: Institute) -> FakeUser:
    return FakeUser(role=Role.INSTITUTE_ADMIN, institute=institute_a)


@pytest.fixture
def admin_b(institute_b: Institute) -> FakeUser:
    return FakeUser(role=Role.INSTITUTE_ADMIN, institute=institute_b)


@pytest.fixture
def super_admin_user() -> FakeUser:
    return FakeUser(role=Role.SUPER_ADMIN, institute_id=None)


@pytest.fixture
def teacher_a(institute_a: Institute) -> FakeUser:
    return FakeUser(role=Role.TEACHER, institute=institute_a)


@pytest.fixture
def sub_admin_a(institute_a: Institute) -> FakeUser:
    return FakeUser(
        role=Role.SUB_ADMIN,
        institute=institute_a,
        allowed_menus=["people", "dashboards"],
    )


@pytest.fixture
def anonymous_user() -> FakeUser:
    return FakeUser(role="", institute_id=None, is_authenticated=False)


def make_user(
    *,
    email: str,
    role: str,
    institute: Institute | None = None,
    password: str = TEST_LOGIN_PASSWORD,
    is_staff: bool = False,
    **extra: object,
) -> User:
    """Persist an accounts.User for integration tests."""
    return User.objects.create_user(
        email=email,
        password=password,
        role=role,
        institute=institute,
        is_staff=is_staff,
        **extra,
    )


@pytest.fixture
def institute_admin_user(institute_a: Institute) -> User:
    return make_user(
        email="admin-a@example.com",
        role=Role.INSTITUTE_ADMIN,
        institute=institute_a,
    )
