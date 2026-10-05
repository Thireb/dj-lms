"""Access mixin behaviour for portal page views."""

from __future__ import annotations

from typing import Any

import pytest
from apps.core.mixins.access import MenuRequiredMixin
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.test import RequestFactory
from django.views.generic import View

from tests.conftest import FakeUser
from tests.ui.support.page_views import (
    DemoAdminDashboard,
    DemoAdminMissingMenuKey,
    DemoTeacherDashboard,
    DemoTeacherEmptyAllowedRoles,
)


def _dispatch(view_cls: type, user: FakeUser, institute: Any | None = None) -> Any:
    rf = RequestFactory()
    request = rf.get("/test/access/")
    request.user = user
    request.institute = institute
    return view_cls.as_view()(request)


@pytest.mark.django_db
def test_sub_admin_without_menu_key_gets_403(
    sub_admin_a: FakeUser, institute_a
) -> None:
    sub_admin_a.allowed_menus = []
    response = _dispatch(DemoAdminMissingMenuKey, sub_admin_a, institute_a)
    assert response.status_code == 403


@pytest.mark.django_db
def test_institute_admin_on_admin_page_without_menu_key_raises(
    admin_a: FakeUser, institute_a
) -> None:
    with pytest.raises(ImproperlyConfigured, match="menu_key"):
        _dispatch(DemoAdminMissingMenuKey, admin_a, institute_a)


@pytest.mark.django_db
def test_sub_admin_empty_allowed_menus_denied_on_admin_dashboard(
    sub_admin_a: FakeUser, institute_a
) -> None:
    sub_admin_a.allowed_menus = []
    response = _dispatch(DemoAdminDashboard, sub_admin_a, institute_a)
    assert response.status_code == 403


@pytest.mark.django_db
def test_role_required_rejects_empty_allowed_roles(
    teacher_a: FakeUser, institute_a
) -> None:
    response = _dispatch(DemoTeacherEmptyAllowedRoles, teacher_a, institute_a)
    assert response.status_code == 403


@pytest.mark.django_db
def test_tenant_required_rejects_missing_institute(
    teacher_a: FakeUser, institute_a
) -> None:
    response = _dispatch(DemoTeacherDashboard, teacher_a, institute=None)
    assert response.status_code == 403


@pytest.mark.django_db
def test_mutation_sensitive_role_required_empty_allowed_roles(
    admin_a: FakeUser, institute_a
) -> None:
    """Fails if RoleRequiredMixin treats empty allowed_roles as allow-all."""

    response = _dispatch(DemoTeacherEmptyAllowedRoles, admin_a, institute_a)
    assert response.status_code == 403


@pytest.mark.django_db
def test_mutation_sensitive_tenant_required_missing_institute(
    teacher_a: FakeUser,
) -> None:
    """Fails if TenantRequiredMixin no longer requires request.institute."""

    response = _dispatch(DemoTeacherDashboard, teacher_a, institute=None)
    assert response.status_code == 403


def test_menu_required_mixin_sub_admin_fail_closed_without_key(
    rf: RequestFactory, sub_admin_a: FakeUser
) -> None:
    class ProbeView(MenuRequiredMixin, View):
        menu_key = None

        def get(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
            return HttpResponse("ok")

    request = rf.get("/")
    request.user = sub_admin_a
    response = ProbeView.as_view()(request)
    assert response.status_code == 403
