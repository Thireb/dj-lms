"""Minimal page views for access and layout tests."""

from __future__ import annotations

from apps.core import menus as menu_keys
from apps.core.roles import Role
from apps.ui.forms.base import TenantModelForm
from apps.ui.views.pages import DashboardPage, FormPage, ListPage
from django.core.exceptions import ValidationError
from tests.testapp.models import TenantProbe


class TenantProbeCreateForm(TenantModelForm):
    class Meta:
        model = TenantProbe
        fields = ["label"]

    def clean_label(self) -> str:
        label = (self.cleaned_data.get("label") or "").strip()
        if not label:
            raise ValidationError("Label is required.")
        return label


class DemoTenantProbeFormPage(FormPage):
    portal = "teacher"
    title = "Create probe"
    active_item = "dashboard"
    allowed_roles = [Role.TEACHER]
    form_class = TenantProbeCreateForm
    success_url = "/test/pages/probe-created/"

    def on_form_valid(self, form: TenantProbeCreateForm) -> None:
        form.save()


class DemoAdminDashboard(DashboardPage):
    portal = "admin"
    title = "Main dashboard"
    menu_key = menu_keys.DASHBOARDS
    allowed_roles = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]


class DemoTeacherDashboard(DashboardPage):
    portal = "teacher"
    title = "Teacher dashboard"
    active_item = "dashboard"
    allowed_roles = [Role.TEACHER]


class DemoAdminPeopleList(ListPage):
    portal = "admin"
    title = "Students"
    menu_key = menu_keys.PEOPLE
    allowed_roles = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]


class DemoAdminMissingMenuKey(DashboardPage):
    """Intentionally misconfigured admin page for mixin tests."""

    _access_test_exclude = True

    portal = "admin"
    title = "Misconfigured"
    menu_key = None
    allowed_roles = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]


class DemoTeacherEmptyAllowedRoles(DashboardPage):
    """Page with no allowed roles — every authenticated user must get 403."""

    portal = "teacher"
    title = "Closed"
    active_item = "dashboard"
    allowed_roles = []


class DemoTeacherInheritsDefaultAllowedRoles(DashboardPage):
    """Inherits PortalPageView allowed_roles default (fail-closed)."""

    portal = "teacher"
    title = "Inherited roles"
    active_item = "dashboard"
