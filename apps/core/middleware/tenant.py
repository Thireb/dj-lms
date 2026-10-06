"""Set the current institute from the authenticated user."""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.urls import Resolver404, resolve

from apps.core.roles import user_institute_id, user_is_super_admin
from apps.core.tenancy import clear_current_institute, set_current_institute
from apps.institutes.models import Institute


class TenantMiddleware:
    """Attach institute context; reject users without a valid active institute."""

    url_names_without_institute: frozenset[str] = frozenset({"accounts:logout"})

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        clear_current_institute()
        request.institute = None
        try:
            user = getattr(request, "user", None)
            if user is not None and getattr(user, "is_authenticated", False):
                if user_is_super_admin(user):
                    return self.get_response(request)
                institute_id = user_institute_id(user)
                if institute_id is None:
                    if self._url_name_allowed_without_institute(request):
                        return self.get_response(request)
                    return HttpResponseForbidden("No institute assigned.")
                try:
                    institute = Institute.objects.get(pk=institute_id)
                except Institute.DoesNotExist:
                    return HttpResponseForbidden("Invalid institute.")
                if not institute.is_active:
                    return HttpResponseForbidden("Institute inactive.")
                request.institute = institute
                set_current_institute(institute)
            return self.get_response(request)
        finally:
            clear_current_institute()

    def _url_name_allowed_without_institute(self, request: HttpRequest) -> bool:
        try:
            match = resolve(request.path_info)
        except Resolver404:
            return False
        url_name = match.url_name
        if match.namespace:
            url_name = f"{match.namespace}:{url_name}"
        return url_name in self.url_names_without_institute
