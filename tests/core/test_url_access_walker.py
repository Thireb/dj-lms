"""Walk every product URL and check the role gate (roadmap 1.4, audit G3).

For each named URL in ``config.urls`` that is not public:
- the view is a ``PortalPageView`` with a non-empty ``allowed_roles``;
- anonymous users are redirected to login;
- every role not in ``allowed_roles`` gets 403;
- at least one allowed role gets through (200, or 405 for POST-only views).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from apps.academics.models import Batch, ClassLabel, Subject
from apps.accounts.models import User
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.people.models import TeacherProfile
from apps.people.services import create_teacher_profile
from apps.ui.views.pages import PortalPageView
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from tests.conftest import make_user

PUBLIC_ALLOWLIST = {
    "accounts:login",
    "accounts:logout",
    "accounts:forgot_password",
    "accounts:set_password",
    "dev_components",
}
SKIPPED_NAMESPACES = {"developer"}  # /django-admin/, gated by middleware tests.


@dataclass(frozen=True)
class Route:
    name: str
    view_class: Any
    kwarg_names: tuple[str, ...]


def _walk(patterns, namespace: str = "") -> list[Route]:
    routes: list[Route] = []
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            child = pattern.namespace or ""
            if child in SKIPPED_NAMESPACES:
                continue
            prefix = f"{namespace}:{child}" if namespace and child else child
            routes += _walk(pattern.url_patterns, prefix or namespace)
        elif isinstance(pattern, URLPattern) and pattern.name:
            name = f"{namespace}:{pattern.name}" if namespace else pattern.name
            routes.append(
                Route(
                    name=name,
                    view_class=getattr(pattern.callback, "view_class", None),
                    kwarg_names=tuple(pattern.pattern.converters),
                )
            )
    return routes


PRODUCT_ROUTES = [
    route
    for route in _walk(get_resolver("config.urls").url_patterns)
    if route.name not in PUBLIC_ALLOWLIST
]


def test_walker_finds_the_product_urls() -> None:
    names = {route.name for route in PRODUCT_ROUTES}
    assert {
        "admin:home",
        "admin:campus",
        "admin:institute_settings",
        "super:institute_list",
        "super:institute_edit",
        "super:institute_status",
        "accounts:profile",
        "admin:batch_list",
        "admin:batch_edit",
        "admin:teacher_list",
        "admin:teacher_edit",
    } <= names


def test_every_route_with_a_pk_has_an_object() -> None:
    # A pk route without a real row would pass the walker with a 404.
    for route in PRODUCT_ROUTES:
        if route.kwarg_names and route.name.startswith("admin:"):
            assert route.name in ROUTE_OBJECTS, route.name


@pytest.mark.parametrize("route", PRODUCT_ROUTES, ids=lambda r: r.name)
def test_every_product_view_declares_roles(route: Route) -> None:
    assert route.view_class is not None, f"{route.name} is a function view"
    assert issubclass(route.view_class, PortalPageView), route.name
    assert route.view_class.allowed_roles, f"{route.name} has no allowed_roles"


# Routes whose pk is not an institute: build a row in the institute instead.
def _name_row(model):
    def build(institute) -> int:
        # unscoped: test setup outside a tenant context.
        row, _ = model.unscoped.get_or_create(institute=institute, name="Walker")
        return row.pk

    return build


def _teacher(institute) -> int:
    # unscoped: test setup outside a tenant context.
    existing = TeacherProfile.unscoped.filter(institute=institute).first()
    if existing is not None:
        return existing.pk
    user = make_user(
        email="teacher-row-walker@example.com",
        role=Role.TEACHER,
        institute=institute,
    )
    with tenant_context(institute):
        return create_teacher_profile(user).pk


ROUTE_OBJECTS = {
    **{
        f"admin:{prefix}_{action}": _name_row(model)
        for prefix, model in (
            ("class", ClassLabel),
            ("batch", Batch),
            ("subject", Subject),
        )
        for action in ("edit", "status")
    },
    "admin:teacher_edit": _teacher,
    "admin:teacher_status": _teacher,
}


ADMIN_PORTAL_ROLES = {Role.INSTITUTE_ADMIN, Role.SUB_ADMIN}


@pytest.mark.parametrize("route", PRODUCT_ROUTES, ids=lambda r: r.name)
def test_admin_portal_views_allow_admin_roles_only(route: Route) -> None:
    # The 403 walk only checks roles outside allowed_roles, so an extra role
    # added to an admin page would pass it unseen.
    if getattr(route.view_class, "portal", None) == "admin":
        assert set(route.view_class.allowed_roles) <= ADMIN_PORTAL_ROLES, route.name


def _url(route: Route, institute) -> str:
    build = ROUTE_OBJECTS.get(route.name)
    pk = build(institute) if build is not None else institute.pk
    kwargs = {name: pk for name in route.kwarg_names}
    return reverse(route.name, kwargs=kwargs)


def _user_for(role: str, institute):
    return make_user(
        email=f"{role}-walker@example.com",
        role=role,
        institute=None if role == Role.SUPER_ADMIN else institute,
    )


@pytest.mark.django_db
@pytest.mark.parametrize("route", PRODUCT_ROUTES, ids=lambda r: r.name)
def test_anonymous_is_redirected_to_login(route: Route, institute_a) -> None:
    response = Client().get(_url(route, institute_a))
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("accounts:login"))


@pytest.mark.django_db
@pytest.mark.parametrize("route", PRODUCT_ROUTES, ids=lambda r: r.name)
def test_roles_outside_allowed_roles_get_403(route: Route, institute_a) -> None:
    allowed = route.view_class.allowed_roles
    denied = [role for role in User.Role.values if role not in allowed]
    for role in denied:
        client = Client()
        client.force_login(_user_for(role, institute_a))
        status = client.get(_url(route, institute_a)).status_code
        assert status == 403, f"{route.name}: {role} got {status}"


@pytest.mark.django_db
@pytest.mark.parametrize("route", PRODUCT_ROUTES, ids=lambda r: r.name)
def test_an_allowed_role_gets_through(route: Route, institute_a) -> None:
    statuses = {}
    for role in route.view_class.allowed_roles:
        client = Client()
        client.force_login(_user_for(role, institute_a))
        statuses[role] = client.get(_url(route, institute_a)).status_code
    assert set(statuses.values()) & {200, 405}, f"{route.name}: {statuses}"
