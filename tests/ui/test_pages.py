from __future__ import annotations

from typing import Any

import pytest
from apps.core.roles import Role
from django.test import RequestFactory
from tests.conftest import FakeUser
from tests.ui.support.page_views import (
    DemoAdminDashboard,
    DemoAdminPeopleList,
    DemoTeacherDashboard,
)

ALL_ROLES = (
    Role.SUPER_ADMIN,
    Role.INSTITUTE_ADMIN,
    Role.SUB_ADMIN,
    Role.TEACHER,
    Role.STUDENT,
    Role.GUARDIAN,
)


def _dispatch(
    view_cls: type,
    user: FakeUser,
    institute: Any | None,
    path: str = "/test/pages/",
) -> Any:
    rf = RequestFactory()
    request = rf.get(path)
    request.user = user
    request.institute = institute
    return view_cls.as_view()(request)


def _user_for_role(role: str | None, institute: Any) -> FakeUser:
    if role is None:
        return FakeUser(role="", institute_id=None, is_authenticated=False)
    if role == Role.SUB_ADMIN:
        return FakeUser(
            role=role,
            institute=institute,
            allowed_menus=["people", "dashboards"],
        )
    if role == Role.SUPER_ADMIN:
        return FakeUser(role=role, institute_id=None)
    return FakeUser(role=role, institute=institute)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "expected_status"),
    [
        (Role.TEACHER, 200),
        (Role.SUPER_ADMIN, 403),
        (Role.INSTITUTE_ADMIN, 403),
        (Role.SUB_ADMIN, 403),
        (Role.STUDENT, 403),
        (Role.GUARDIAN, 403),
        (None, 302),
    ],
    ids=[
        "teacher",
        "super_admin",
        "institute_admin",
        "sub_admin",
        "student",
        "guardian",
        "anonymous",
    ],
)
def test_teacher_dashboard_access_by_role(
    role: str | None, expected_status: int, institute_a
) -> None:
    user = _user_for_role(role, institute_a)
    response = _dispatch(
        DemoTeacherDashboard, user, institute_a, "/test/pages/teacher-dashboard/"
    )
    assert response.status_code == expected_status
    if expected_status == 200:
        assert b"Teacher dashboard" in response.content
    if role is None:
        assert "/accounts/login/" in response.url


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role",
    [r for r in ALL_ROLES if r not in (Role.INSTITUTE_ADMIN, Role.SUB_ADMIN)] + [None],
    ids=[
        "super_admin",
        "teacher",
        "student",
        "guardian",
        "anonymous",
    ],
)
def test_admin_dashboard_forbidden_for_non_admin_roles(
    role: str | None, institute_a
) -> None:
    user = _user_for_role(role, institute_a)
    response = _dispatch(
        DemoAdminDashboard, user, institute_a, "/test/pages/admin-dashboard/"
    )
    if role is None:
        assert response.status_code == 302
        assert "/accounts/login/" in response.url
    else:
        assert response.status_code == 403


@pytest.mark.django_db
def test_admin_dashboard_allowed_for_institute_admin(
    admin_a: FakeUser, institute_a
) -> None:
    response = _dispatch(
        DemoAdminDashboard, admin_a, institute_a, "/test/pages/admin-dashboard/"
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_dashboard_allowed_for_sub_admin_with_menu(
    sub_admin_a: FakeUser, institute_a
) -> None:
    response = _dispatch(
        DemoAdminDashboard, sub_admin_a, institute_a, "/test/pages/admin-dashboard/"
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_dashboard_forbidden_for_sub_admin_without_menu(
    sub_admin_a: FakeUser, institute_a
) -> None:
    sub_admin_a.allowed_menus = ["people"]
    response = _dispatch(
        DemoAdminDashboard, sub_admin_a, institute_a, "/test/pages/admin-dashboard/"
    )
    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role",
    [r for r in ALL_ROLES if r not in (Role.INSTITUTE_ADMIN, Role.SUB_ADMIN)] + [None],
    ids=[
        "super_admin",
        "teacher",
        "student",
        "guardian",
        "anonymous",
    ],
)
def test_admin_people_forbidden_for_non_admin_roles(
    role: str | None, institute_a
) -> None:
    user = _user_for_role(role, institute_a)
    response = _dispatch(
        DemoAdminPeopleList, user, institute_a, "/test/pages/admin-people/"
    )
    if role is None:
        assert response.status_code == 302
        assert "/accounts/login/" in response.url
    else:
        assert response.status_code == 403


@pytest.mark.django_db
def test_admin_people_allowed_for_institute_admin(
    admin_a: FakeUser, institute_a
) -> None:
    response = _dispatch(
        DemoAdminPeopleList, admin_a, institute_a, "/test/pages/admin-people/"
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_people_allowed_for_sub_admin_with_menu(
    sub_admin_a: FakeUser, institute_a
) -> None:
    response = _dispatch(
        DemoAdminPeopleList, sub_admin_a, institute_a, "/test/pages/admin-people/"
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_people_forbidden_for_sub_admin_without_menu(
    sub_admin_a: FakeUser, institute_a
) -> None:
    sub_admin_a.allowed_menus = ["dashboards"]
    response = _dispatch(
        DemoAdminPeopleList, sub_admin_a, institute_a, "/test/pages/admin-people/"
    )
    assert response.status_code == 403
