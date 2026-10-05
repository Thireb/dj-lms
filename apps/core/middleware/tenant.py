"""Set the current institute from the authenticated user."""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden

from apps.core.roles import _is_super_admin, _user_institute_id
from apps.core.tenancy import clear_current_institute, set_current_institute
from apps.institutes.models import Institute


class TenantMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        clear_current_institute()
        request.institute = None
        try:
            user = getattr(request, "user", None)
            if user is not None and getattr(user, "is_authenticated", False):
                if _is_super_admin(user):
                    return self.get_response(request)
                institute_id = _user_institute_id(user)
                if institute_id is None:
                    return HttpResponseForbidden("No institute assigned.")
                try:
                    institute = Institute.objects.get(pk=institute_id)
                except Institute.DoesNotExist:
                    return HttpResponseForbidden("Invalid institute.")
                request.institute = institute
                set_current_institute(institute)
            return self.get_response(request)
        finally:
            clear_current_institute()
