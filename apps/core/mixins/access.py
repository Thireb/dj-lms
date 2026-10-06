"""Role, tenant, and admin menu access mixins for class-based views."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden

from apps.core.roles import Role, user_is_super_admin, user_role


class RoleRequiredMixin:
    """Deny dispatch unless the user's role is in ``allowed_roles``."""

    allowed_roles: list[str] = []

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not self.allowed_roles:
            return HttpResponseForbidden("Forbidden.")
        user = request.user
        if not getattr(user, "is_authenticated", False):
            return HttpResponseForbidden("Forbidden.")
        role = user_role(user)
        if role not in self.allowed_roles:
            return HttpResponseForbidden("Forbidden.")
        return super().dispatch(request, *args, **kwargs)


class TenantRequiredMixin:
    """Require a tenant institute on the request (super admin exempt)."""

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        user = request.user
        if getattr(user, "is_authenticated", False) and user_is_super_admin(user):
            return super().dispatch(request, *args, **kwargs)
        institute = getattr(request, "institute", None)
        if institute is None:
            return HttpResponseForbidden("No institute assigned.")
        return super().dispatch(request, *args, **kwargs)


class MenuRequiredMixin:
    """Admin views: sub_admin must have ``menu_key`` in ``user.allowed_menus``."""

    menu_key: str | None = None

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        key = getattr(self, "menu_key", None) or None
        portal = getattr(self, "portal", None)
        user = request.user
        authenticated = getattr(user, "is_authenticated", False)
        role = user_role(user) if authenticated else None

        if role == Role.SUB_ADMIN and not key:
            return HttpResponseForbidden("Forbidden.")

        if (
            portal == "admin"
            and not key
            and role in (Role.INSTITUTE_ADMIN, Role.SUB_ADMIN)
        ):
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} sets portal='admin' "
                "but menu_key is missing."
            )

        if key and role == Role.SUB_ADMIN:
            allowed = getattr(user, "allowed_menus", None) or []
            if key not in allowed:
                return HttpResponseForbidden("Forbidden.")
        return super().dispatch(request, *args, **kwargs)
