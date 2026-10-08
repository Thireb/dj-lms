"""Set the current institute from the authenticated user."""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from django.urls import Resolver404, resolve

from apps.core.responses import blocked_account_response
from apps.core.roles import user_institute_id, user_is_super_admin
from apps.core.tenancy import clear_current_institute, set_current_institute
from apps.institutes.models import Institute

NO_INSTITUTE = "Your account has no institute. Contact the institute office."
INSTITUTE_INACTIVE = (
    "Your institute is not active. Contact your institute administrator."
)


class TenantMiddleware:
    """Attach institute context; reject users without a valid active institute."""

    url_names_without_institute: frozenset[str] = frozenset(
        {
            "accounts:logout",
            "accounts:login",
            "accounts:forgot_password",
            "accounts:set_password",
        }
    )

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
                if self._url_name_allowed_without_institute(request):
                    return self.get_response(request)
                institute_id = user_institute_id(user)
                if institute_id is None:
                    return blocked_account_response(request, NO_INSTITUTE)
                try:
                    institute = Institute.objects.get(pk=institute_id)
                except Institute.DoesNotExist:
                    return blocked_account_response(request, NO_INSTITUTE)
                if not institute.is_active:
                    return blocked_account_response(request, INSTITUTE_INACTIVE)
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
