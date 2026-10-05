"""Tenant manager and for_user scoping."""

from __future__ import annotations

import pytest
from apps.core.tenancy import clear_current_institute, set_current_institute
from apps.institutes.models import Institute

from tests.conftest import FakeUser
from tests.testapp.models import TenantProbe


@pytest.mark.django_db
def test_for_user_isolates_by_institute(
    probe_a: TenantProbe,
    probe_b: TenantProbe,
    admin_a: FakeUser,
    admin_b: FakeUser,
) -> None:
    visible_a = list(TenantProbe.objects.for_user(admin_a))
    visible_b = list(TenantProbe.objects.for_user(admin_b))

    assert visible_a == [probe_a]
    assert visible_b == [probe_b]


@pytest.mark.django_db
def test_super_admin_sees_all_institutes(
    probe_a: TenantProbe,
    probe_b: TenantProbe,
    super_admin_user: FakeUser,
) -> None:
    visible = set(TenantProbe.objects.for_user(super_admin_user))
    assert visible == {probe_a, probe_b}


@pytest.mark.django_db
def test_user_without_institute_sees_nothing(probe_a: TenantProbe) -> None:
    user = FakeUser(role="teacher", institute_id=None)
    assert list(TenantProbe.objects.for_user(user)) == []


@pytest.mark.django_db
def test_manager_filters_by_tenant_context(
    institute_a: Institute,
    institute_b: Institute,
    probe_a: TenantProbe,
    probe_b: TenantProbe,
) -> None:
    clear_current_institute()
    set_current_institute(institute_a)
    try:
        visible = set(TenantProbe.objects.all())
    finally:
        clear_current_institute()

    assert visible == {probe_a}
    assert probe_b not in visible


@pytest.mark.django_db
def test_manager_without_context_returns_unfiltered(
    probe_a: TenantProbe,
    probe_b: TenantProbe,
) -> None:
    clear_current_institute()
    visible = set(TenantProbe.objects.all())
    assert visible == {probe_a, probe_b}
