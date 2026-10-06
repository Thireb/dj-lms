from __future__ import annotations

from typing import Any

import pytest
from apps.core import menus as menu_keys
from apps.core.roles import Role
from apps.ui.views.pages import PortalPageView
from django.test import RequestFactory
from tests.conftest import FakeUser
from tests.ui.support.page_views import DemoTeacherInheritsDefaultAllowedRoles

ALL_ROLES = (
    Role.SUPER_ADMIN,
    Role.INSTITUTE_ADMIN,
    Role.SUB_ADMIN,
    Role.TEACHER,
    Role.STUDENT,
    Role.GUARDIAN,
)


def _dispatch(view_cls: type, user: FakeUser, institute: Any | None) -> Any:
    rf = RequestFactory()
    request = rf.get("/test/access/inherited/")
    request.user = user
    request.institute = institute
    return view_cls.as_view()(request)


def _user_for_role(role: str | None, institute: Any) -> FakeUser:
    if role is None:
        return FakeUser(role="", institute_id=None, is_authenticated=False)
    if role == Role.SUPER_ADMIN:
        return FakeUser(role=role, institute_id=None)
    return FakeUser(role=role, institute=institute)


def _all_portal_page_view_subclasses() -> set[type]:
    pending: list[type] = [PortalPageView]
    seen: set[type] = set()
    while pending:
        cls = pending.pop()
        if cls in seen:
            continue
        seen.add(cls)
        pending.extend(cls.__subclasses__())
    return seen


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role",
    list(ALL_ROLES) + [None],
    ids=[
        "super_admin",
        "institute_admin",
        "sub_admin",
        "teacher",
        "student",
        "guardian",
        "anonymous",
    ],
)
def test_page_without_declared_allowed_roles_forbids_everyone(
    role: str | None, institute_a
) -> None:
    user = _user_for_role(role, institute_a)
    response = _dispatch(DemoTeacherInheritsDefaultAllowedRoles, user, institute_a)
    assert response.status_code == 403


@pytest.mark.django_db
def test_mutation_sensitive_default_allowed_roles_not_allow_all(
    teacher_a: FakeUser, institute_a
) -> None:
    """Fails if PortalPageView.allowed_roles default becomes a non-empty allow list."""

    assert PortalPageView.allowed_roles == []
    response = _dispatch(DemoTeacherInheritsDefaultAllowedRoles, teacher_a, institute_a)
    assert response.status_code == 403


def test_every_admin_portal_page_view_has_exactly_one_access_mode() -> None:
    """C10: admin portal pages declare menu_key, self_service, or admin_only."""
    valid_keys = set(menu_keys.ADMIN_MENU_KEYS)
    offenders: list[str] = []
    for cls in sorted(_all_portal_page_view_subclasses(), key=lambda c: c.__name__):
        if getattr(cls, "_access_test_exclude", False):
            continue
        if getattr(cls, "portal", None) != "admin":
            continue
        self_service = bool(getattr(cls, "self_service", False))
        admin_only = bool(getattr(cls, "admin_only", False))
        key = getattr(cls, "menu_key", None)
        has_menu = key in valid_keys
        mode_count = sum((self_service, admin_only, has_menu))
        name = f"{cls.__module__}.{cls.__name__}"
        if mode_count != 1:
            offenders.append(
                f"{name} must set exactly one of menu_key, self_service, admin_only "
                f"(got menu_key={key!r}, self_service={self_service}, "
                f"admin_only={admin_only})"
            )
    assert offenders == []
