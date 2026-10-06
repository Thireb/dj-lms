"""TenantAdmin uses unscoped so changelist works without tenant context."""

from __future__ import annotations

import pytest
from apps.accounts.models import User
from apps.core.admin import TenantAdmin
from apps.core.tenancy import clear_current_institute
from apps.institutes.models import Institute
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import AnonymousUser
from django.test import Client

from tests.conftest import FakeUser
from tests.testapp.models import TenantProbe


class PlainTenantProbeAdmin(admin.ModelAdmin):
    pass


@pytest.mark.django_db
def test_tenant_admin_changelist_without_institute_context(
    institute_a: Institute,
    institute_b: Institute,
) -> None:
    clear_current_institute()
    TenantProbe.unscoped.create(institute=institute_a, label="a")
    TenantProbe.unscoped.create(institute=institute_b, label="b")

    site = AdminSite()
    model_admin = TenantAdmin(TenantProbe, site)
    request = type("Req", (), {"user": AnonymousUser()})()

    qs = model_admin.get_queryset(request)
    assert qs.count() == 2


@pytest.mark.django_db
def test_plain_model_admin_changelist_empty_without_institute_context(
    institute_a: Institute,
) -> None:
    clear_current_institute()
    TenantProbe.unscoped.create(institute=institute_a, label="a")

    site = AdminSite()
    model_admin = PlainTenantProbeAdmin(TenantProbe, site)
    request = type("Req", (), {"user": FakeUser(role="super_admin")})()

    qs = model_admin.get_queryset(request)
    assert qs.count() == 0


@pytest.mark.django_db
def test_tenant_admin_changelist_forbidden_for_staff_non_super_admin(
    institute_a: Institute,
) -> None:
    TenantProbe.unscoped.create(institute=institute_a, label="a")
    User.objects.create_user(
        email="staffdev@example.com",
        password="pass",
        role=User.Role.INSTITUTE_ADMIN,
        institute=institute_a,
        is_staff=True,
    )
    client = Client()
    assert client.login(username="staffdev@example.com", password="pass")

    response = client.get("/django-admin/testapp/tenantprobe/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_tenant_admin_has_view_permission_only_for_super_admin() -> None:
    site = AdminSite()
    model_admin = TenantAdmin(TenantProbe, site)
    staff_teacher = FakeUser(role="teacher")
    staff_teacher.is_staff = True  # noqa: SLF001
    super_admin = FakeUser(role="super_admin", institute_id=None)

    assert not model_admin.has_view_permission(
        type("Req", (), {"user": staff_teacher})()
    )
    assert model_admin.has_view_permission(type("Req", (), {"user": super_admin})())


@pytest.mark.django_db
def test_tenant_admin_has_add_permission_only_for_super_admin() -> None:
    site = AdminSite()
    model_admin = TenantAdmin(TenantProbe, site)
    institute_admin = FakeUser(role="institute_admin", institute_id=1)
    institute_admin.is_staff = True  # noqa: SLF001
    institute_admin.is_superuser = True  # noqa: SLF001
    super_admin = FakeUser(role="super_admin", institute_id=None)

    assert not model_admin.has_add_permission(
        type("Req", (), {"user": institute_admin})()
    )
    assert model_admin.has_add_permission(type("Req", (), {"user": super_admin})())


@pytest.mark.django_db
def test_tenant_admin_has_delete_permission_only_for_super_admin() -> None:
    site = AdminSite()
    model_admin = TenantAdmin(TenantProbe, site)
    institute_admin = FakeUser(role="institute_admin", institute_id=1)
    institute_admin.is_staff = True  # noqa: SLF001
    institute_admin.is_superuser = True  # noqa: SLF001
    super_admin = FakeUser(role="super_admin", institute_id=None)

    assert not model_admin.has_delete_permission(
        type("Req", (), {"user": institute_admin})()
    )
    assert model_admin.has_delete_permission(type("Req", (), {"user": super_admin})())
