"""Role, tenant, and admin menu access mixins for class-based views."""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden

from apps.core.roles import Role, _is_super_admin, _user_role


class RoleRequiredMixin:
    """Deny dispatch unless the user's role is in ``allowed_roles``."""

    allowed_roles: list[str] = []

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not self.allowed_roles:
            return HttpResponseForbidden("Forbidden.")
        user = request.user
        if not getattr(user, "is_authenticated", False):
            return HttpResponseForbidden("Forbidden.")
        role = _user_role(user)
        if role not in self.allowed_roles:
            return HttpResponseForbidden("Forbidden.")
        return super().dispatch(request, *args, **kwargs)


class TenantRequiredMixin:
    """Require a tenant institute on the request (super admin exempt)."""

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        user = request.user
        if getattr(user, "is_authenticated", False) and _is_super_admin(user):
            return super().dispatch(request, *args, **kwargs)
        institute = getattr(request, "institute", None)
        if institute is None:
            return HttpResponseForbidden("No institute assigned.")
        return super().dispatch(request, *args, **kwargs)


class MenuRequiredMixin:
    """Admin views: sub_admin must have ``menu_key`` in ``user.allowed_menus``."""

    menu_key: str | None = None

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        key = getattr(self, "menu_key", None)
        if key:
            user = request.user
            if _user_role(user) == Role.SUB_ADMIN:
                allowed = getattr(user, "allowed_menus", None) or []
                if key not in allowed:
                    return HttpResponseForbidden("Forbidden.")
        return super().dispatch(request, *args, **kwargs)
