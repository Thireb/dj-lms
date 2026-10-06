"""Role, tenant, and admin menu access mixins for class-based views."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.template.loader import render_to_string

from apps.core.roles import Role, user_is_super_admin, user_role


def requires_feature(feature_key: str):
    """Class decorator setting ``feature_key`` on a view."""

    def wrap(cls: type) -> type:
        cls.feature_key = feature_key
        return cls

    return wrap


class RoleRequiredMixin:
    """Deny dispatch unless the user's role is in ``allowed_roles``."""

    allowed_roles: list[str] = []

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not self.allowed_roles:
            return HttpResponseForbidden("Forbidden.")
        user = request.user
        if not getattr(user, "is_authenticated", False):
            return redirect_to_login(request.get_full_path())
        role = user_role(user)
        if role not in self.allowed_roles:
            return HttpResponseForbidden("Forbidden.")
        return super().dispatch(request, *args, **kwargs)


class FeatureRequiredMixin:
    """Deny dispatch when the institute plan lacks ``feature_key``."""

    feature_key: str | None = None

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        key = getattr(self, "feature_key", None)
        if key:
            user = request.user
            if getattr(user, "is_authenticated", False) and user_is_super_admin(user):
                return super().dispatch(request, *args, **kwargs)
            institute = getattr(request, "institute", None) or getattr(
                user, "institute", None
            )
            features = getattr(institute, "features", None) or frozenset()
            if key not in features:
                html = render_to_string(
                    "ui/pages/feature_not_available.html",
                    {"feature_key": key},
                    request=request,
                )
                return HttpResponse(html, status=403)
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
    self_service: bool = False
    admin_only: bool = False

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if getattr(self, "admin_only", False):
            configured = getattr(self, "allowed_roles", [])
            if configured != [Role.INSTITUTE_ADMIN]:
                raise ImproperlyConfigured(
                    f"{self.__class__.__name__} sets admin_only=True but "
                    f"allowed_roles={configured!r}; must be exactly "
                    f"[{Role.INSTITUTE_ADMIN!r}]."
                )
            return super().dispatch(request, *args, **kwargs)

        if getattr(self, "self_service", False):
            return super().dispatch(request, *args, **kwargs)

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
