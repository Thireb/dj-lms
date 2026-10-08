"""Close the student portal for blocked students (roadmap 2.7, SPEC 6.2)."""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from django.urls import Resolver404, resolve

from apps.core.roles import Role, user_role
from apps.people.services import student_portal_blocked
from apps.people.views import access_paused_response

STUDENT_NAMESPACE = "student"


class StudentPortalAccessMiddleware:
    """Every /student/ page shows "Access paused" while the student is blocked.

    Runs after TenantMiddleware, so the tenant context is set. Account pages
    (sign out, profile) stay open; the guardian portal is never blocked.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if (
            user is not None
            and getattr(user, "is_authenticated", False)
            and user_role(user) == Role.STUDENT
            and self._in_student_portal(request)
            and student_portal_blocked(user)
        ):
            return access_paused_response(request)
        return self.get_response(request)

    @staticmethod
    def _in_student_portal(request: HttpRequest) -> bool:
        try:
            return resolve(request.path_info).namespace == STUDENT_NAMESPACE
        except Resolver404:
            return False
