"""Minimal signed-in landing pages per portal (post-login fallback targets)."""

from __future__ import annotations

from typing import Any

from django.urls import reverse

from apps.core.roles import Role
from apps.ui.components.actions import SignOutForm
from apps.ui.components.layout import SectionCard
from apps.ui.views.pages import DashboardPage


class PortalHomePage(DashboardPage):
    """Signed-in home with a sign-out action until real dashboards exist."""

    page_layout = "dashboard"
    home_message = "You are signed in."

    def get_sections(self) -> list[Any]:
        return [
            SectionCard(
                title="Home",
                body=self.home_message,
            ),
        ]

    def get_actions(self) -> list[Any]:
        return [SignOutForm(logout_url=reverse("accounts:logout"))]


class TeacherPortalHomePage(PortalHomePage):
    portal = "teacher"
    title = "Teacher home"
    active_item = "dashboard"
    allowed_roles = [Role.TEACHER]
    home_message = "Teacher portal home."


class StudentPortalHomePage(PortalHomePage):
    portal = "student"
    title = "Student home"
    active_item = "dashboard"
    allowed_roles = [Role.STUDENT]
    home_message = "Student portal home."


class GuardianPortalHomePage(PortalHomePage):
    portal = "guardian"
    title = "Guardian home"
    active_item = "dashboard"
    allowed_roles = [Role.GUARDIAN]
    home_message = "Guardian portal home."


class SuperAdminPortalHomePage(PortalHomePage):
    portal = "super"
    title = "Super admin home"
    allowed_roles = [Role.SUPER_ADMIN]
    active_item = "institutes"
    home_message = "Super admin signed in. Manage institutes from the menu."
