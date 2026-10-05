"""Shared pytest fixtures for tenant tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from apps.core.roles import Role
from apps.institutes.models import Institute

from tests.testapp.models import TenantProbe


@dataclass
class FakeUser:
    """Minimal user stand-in until apps.accounts exists."""

    role: str
    institute_id: int | None = None
    institute: Institute | None = None
    timezone: str | None = None
    is_authenticated: bool = True

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
def anonymous_user() -> FakeUser:
    return FakeUser(role="", institute_id=None, is_authenticated=False)
