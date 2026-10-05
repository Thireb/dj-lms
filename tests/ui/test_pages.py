from __future__ import annotations

import pytest
from apps.core.roles import Role
from django.test import RequestFactory
from tests.conftest import FakeUser
from tests.ui.support.page_views import (
    DemoAdminDashboard,
    DemoAdminPeopleList,
    DemoTeacherDashboard,
)


@pytest.mark.django_db
def test_teacher_dashboard_allowed(
    rf: RequestFactory, teacher_a: FakeUser, institute_a
) -> None:
    request = rf.get("/test/pages/teacher-dashboard/")
    request.user = teacher_a
    request.institute = institute_a
    response = DemoTeacherDashboard.as_view()(request)
    assert response.status_code == 200
    assert b"Teacher dashboard" in response.content


@pytest.mark.django_db
def test_teacher_dashboard_forbidden_for_student(
    rf: RequestFactory, institute_a
) -> None:
    student = FakeUser(role=Role.STUDENT, institute=institute_a)
    request = rf.get("/test/pages/teacher-dashboard/")
    request.user = student
    request.institute = institute_a
    response = DemoTeacherDashboard.as_view()(request)
    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_dashboard_allowed_for_institute_admin(
    rf: RequestFactory, admin_a: FakeUser, institute_a
) -> None:
    request = rf.get("/test/pages/admin-dashboard/")
    request.user = admin_a
    request.institute = institute_a
    response = DemoAdminDashboard.as_view()(request)
    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_people_forbidden_for_sub_admin_without_menu(
    rf: RequestFactory, sub_admin_a: FakeUser, institute_a
) -> None:
    sub_admin_a.allowed_menus = ["dashboards"]
    request = rf.get("/test/pages/admin-people/")
    request.user = sub_admin_a
    request.institute = institute_a
    response = DemoAdminPeopleList.as_view()(request)
    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_people_allowed_for_sub_admin_with_menu(
    rf: RequestFactory, sub_admin_a: FakeUser, institute_a
) -> None:
    request = rf.get("/test/pages/admin-people/")
    request.user = sub_admin_a
    request.institute = institute_a
    response = DemoAdminPeopleList.as_view()(request)
    assert response.status_code == 200
