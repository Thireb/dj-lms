"""Activate the request user's timezone for template rendering."""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from apps.core.timezone_utils import activate_timezone_for_user, deactivate_timezone


class TimezoneMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            institute = getattr(request, "institute", None)
            activate_timezone_for_user(user, institute=institute)
        try:
            return self.get_response(request)
        finally:
            deactivate_timezone()
