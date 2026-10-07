"""Developer admin pages for profiles (super admin only, no add)."""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.people.services import enrol_guardian

from tests.conftest import TEST_LOGIN_PASSWORD, make_user
from tests.people.conftest import student, teacher

CHANGELISTS = [
    "studentprofile",
    "teacherprofile",
    "guardianprofile",
    "guardianstudentlink",
]


@pytest.fixture
def super_client(client):
    user = make_user(
        email="su@example.com",
        role=Role.SUPER_ADMIN,
        is_staff=True,
        is_superuser=True,
    )
    client.force_login(user)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize("model", CHANGELISTS)
def test_super_admin_sees_profile_changelist(super_client, institute_a, model):
    child = student(institute_a, "s@example.com")
    teacher(institute_a, "t@example.com")
    with tenant_context(institute_a):
        enrol_guardian(child, email="g@example.com", password=TEST_LOGIN_PASSWORD)

    response = super_client.get(f"/django-admin/people/{model}/")

    assert response.status_code == 200
    assert response.context["cl"].result_count == 1


@pytest.mark.django_db
def test_student_change_page_shows_code(super_client, institute_a):
    profile = student(institute_a, "s@example.com")

    response = super_client.get(
        f"/django-admin/people/studentprofile/{profile.pk}/change/"
    )

    assert response.status_code == 200
    assert "STU-001" in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("model", CHANGELISTS)
def test_profiles_cannot_be_added_in_admin(super_client, model):
    response = super_client.get(f"/django-admin/people/{model}/add/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_institute_admin_cannot_open_profile_admin(client, institute_a):
    user = make_user(
        email="ad@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_a
    )
    client.force_login(user)

    response = client.get("/django-admin/people/studentprofile/")

    assert response.status_code == 403
