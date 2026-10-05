"""Minimal page views for access and layout tests."""

from __future__ import annotations

from apps.core import menus as menu_keys
from apps.core.roles import Role
from apps.ui.views.pages import DashboardPage, ListPage


class DemoAdminDashboard(DashboardPage):
    portal = "admin"
    title = "Main dashboard"
    menu_key = menu_keys.DASHBOARDS
    allowed_roles = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]


class DemoTeacherDashboard(DashboardPage):
    portal = "teacher"
    title = "Teacher dashboard"
    menu_key = "dashboard"
    allowed_roles = [Role.TEACHER]


class DemoAdminPeopleList(ListPage):
    portal = "admin"
    title = "Students"
    menu_key = menu_keys.PEOPLE
    allowed_roles = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]
