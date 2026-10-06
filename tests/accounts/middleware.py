"""Test-only middleware stubs until SubAdminProfile exists (roadmap 1.2)."""

from __future__ import annotations

from collections.abc import Callable

from apps.core.roles import Role
from django.http import HttpRequest, HttpResponse


class SubAdminTestMenuMiddleware:
    """Attach allowed_menus for sub_admin users during integration tests."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if (
            user is not None
            and getattr(user, "is_authenticated", False)
            and getattr(user, "role", None) == Role.SUB_ADMIN
            and not getattr(user, "allowed_menus", None)
        ):
            user.allowed_menus = ["dashboards", "account"]
        return self.get_response(request)
