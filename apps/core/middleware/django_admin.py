"""Restrict Django's built-in admin to product super admins only."""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden

from apps.core.roles import user_is_super_admin


class DjangoAdminGateMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path_info.startswith("/django-admin/"):
            user = getattr(request, "user", None)
            if user is None or not getattr(user, "is_authenticated", False):
                return self.get_response(request)
            if not user_is_super_admin(user):
                return HttpResponseForbidden(
                    "Django admin is restricted to super admins."
                )
        return self.get_response(request)
