"""Close the student portal for blocked students (roadmap 2.7, SPEC 6.2)."""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from django.urls import Resolver404, resolve

from apps.core.roles import Role, user_role
from apps.people.services import student_portal_blocked
from apps.people.views import access_paused_response

STUDENT_NAMESPACE = "student"
OPEN_PAGE_PREFIX = "message_"  # Messages stay open while blocked (P6-8)


class StudentPortalAccessMiddleware:
    """Every /student/ page shows "Access paused" while the student is blocked.

    Runs after TenantMiddleware, so the tenant context is set. Account pages
    (sign out, profile) stay open; the guardian portal is never blocked.
    Messages stay open too, so a blocked student can write to the office
    (owner decision 2026-10-16, Phase 6 audit P6-8).
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if (
            user is not None
            and getattr(user, "is_authenticated", False)
            and user_role(user) == Role.STUDENT
            and self._closed_page(request)
            and student_portal_blocked(user)
        ):
            return access_paused_response(request)
        return self.get_response(request)

    @staticmethod
    def _closed_page(request: HttpRequest) -> bool:
        """A student portal page other than Messages."""
        try:
            match = resolve(request.path_info)
        except Resolver404:
            return False
        if match.namespace != STUDENT_NAMESPACE:
            return False
        return not (match.url_name or "").startswith(OPEN_PAGE_PREFIX)
