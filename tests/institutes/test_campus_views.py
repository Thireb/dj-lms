"""Campus profile admin view."""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from django.test import Client
from django.urls import reverse
from tests.conftest import make_user


@pytest.mark.django_db
def test_campus_ok_for_institute_admin(client: Client, institute_a) -> None:
    user = make_user(
        email="admin@example.com",
        role=Role.INSTITUTE_ADMIN,
        institute=institute_a,
    )
    client.force_login(user)
    assert client.get(reverse("admin:campus")).status_code == 200


@pytest.mark.django_db
def test_campus_ok_for_sub_admin_with_institute_menu(institute_a) -> None:
    from apps.institutes.views import CampusProfilePage
    from django.test import RequestFactory

    user = make_user(
        email="sub@example.com",
        role=Role.SUB_ADMIN,
        institute=institute_a,
    )
    user.allowed_menus = ["institute"]
    request = RequestFactory().get("/admin/campus/")
    request.user = user
    request.institute = institute_a
    response = CampusProfilePage.as_view()(request)
    assert response.status_code == 200


@pytest.mark.django_db
def test_campus_forbidden_for_teacher(client: Client, institute_a) -> None:
    user = make_user(
        email="t@example.com",
        role=Role.TEACHER,
        institute=institute_a,
    )
    client.force_login(user)
    assert client.get(reverse("admin:campus")).status_code == 403


@pytest.mark.django_db
def test_campus_invalid_post_does_not_show_unsaved_name(
    client: Client, institute_a
) -> None:
    client.force_login(
        make_user(
            email="admin@example.com",
            role=Role.INSTITUTE_ADMIN,
            institute=institute_a,
        )
    )
    response = client.post(
        reverse("admin:campus"),
        {"name": "Unsaved Name", "email": "not-an-email"},
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert "Enter a valid email address" in html
    assert html.count("Unsaved Name") == 1  # only inside the form input
    assert response.wsgi_request.institute.name == "Institute A"
    institute_a.refresh_from_db()
    assert institute_a.name == "Institute A"


@pytest.mark.django_db
def test_campus_valid_post_saves(client: Client, institute_a) -> None:
    client.force_login(
        make_user(
            email="admin@example.com",
            role=Role.INSTITUTE_ADMIN,
            institute=institute_a,
        )
    )
    response = client.post(
        reverse("admin:campus"),
        {
            "name": "North Campus",
            "address": "1 Fake Street",
            "phone": "000-0000",
            "email": "office@example.com",
        },
    )
    assert response.status_code == 302
    institute_a.refresh_from_db()
    assert institute_a.name == "North Campus"
    assert institute_a.email == "office@example.com"
