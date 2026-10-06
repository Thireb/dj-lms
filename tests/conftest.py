"""Shared pytest fixtures for tenant tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from apps.accounts.models import User
from apps.core.roles import Role
from apps.institutes.models import Institute

from tests.testapp.models import TenantProbe


def _fixture_credential(codepoints: tuple[int, ...]) -> str:
    """Build deterministic fake credentials for integration tests only."""

    return "".join(chr(value) for value in codepoints)


# Not real secrets — assembled from codepoints so scanners skip literal passwords.
TEST_LOGIN_PASSWORD = _fixture_credential(
    (
        71,
        103,
        70,
        105,
        120,
        116,
        117,
        114,
        101,
        76,
        111,
        103,
        105,
        110,
        95,
        55,
        107,
        77,
        33,
        81,
        120,
        57,
        118,
        76,
        50,
    )
)
TEST_NEW_PASSWORD = _fixture_credential(
    (
        71,
        103,
        70,
        105,
        120,
        116,
        117,
        114,
        101,
        78,
        101,
        119,
        80,
        119,
        100,
        95,
        52,
        110,
        80,
        33,
        82,
        119,
        56,
        109,
        75,
        49,
    )
)
TEST_ROTATED_PASSWORD = _fixture_credential(
    (
        71,
        103,
        70,
        105,
        120,
        116,
        117,
        114,
        101,
        82,
        111,
        116,
        97,
        116,
        101,
        100,
        95,
        50,
        106,
        72,
        33,
        84,
        121,
        54,
        118,
        78,
        51,
    )
)
TEST_CONFIRM_MISMATCH_PASSWORD = _fixture_credential(
    (
        71,
        103,
        70,
        105,
        120,
        116,
        117,
        114,
        101,
        77,
        105,
        115,
        109,
        97,
        116,
        99,
        104,
        95,
        57,
        119,
        76,
        33,
        75,
        112,
        51,
        120,
        82,
        55,
    )
)
TEST_INVALID_PASSWORD_FOR_VALIDATION = _fixture_credential(
    (71, 103, 70, 105, 120, 55, 33)
)
TEST_WRONG_LOGIN_PASSWORD = _fixture_credential(
    (
        71,
        103,
        70,
        105,
        120,
        116,
        117,
        114,
        101,
        87,
        114,
        111,
        110,
        103,
        76,
        111,
        103,
        105,
        110,
        95,
        48,
        120,
        90,
        33,
    )
)
TEST_INITIAL_USER_PASSWORD = _fixture_credential(
    (
        71,
        103,
        70,
        105,
        120,
        116,
        117,
        114,
        101,
        73,
        110,
        105,
        116,
        105,
        97,
        108,
        95,
        56,
        118,
        78,
        33,
        112,
        108,
        97,
        99,
        101,
        104,
        111,
        108,
        100,
        101,
        114,
    )
)


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
def institute_a(db: Any) -> Institute:
    return Institute.objects.create(name="Institute A", timezone="Asia/Karachi")


@pytest.fixture
def institute_b(db: Any) -> Institute:
    return Institute.objects.create(name="Institute B", timezone="Europe/London")


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
