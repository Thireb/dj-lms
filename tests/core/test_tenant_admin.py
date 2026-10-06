"""TenantAdmin uses unscoped so changelist works without tenant context."""

from __future__ import annotations

import pytest
from apps.core.admin import TenantAdmin
from apps.core.tenancy import clear_current_institute
from apps.institutes.models import Institute
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import AnonymousUser

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
