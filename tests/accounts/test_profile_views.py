"""Profile and change-password portal pages (roadmap 1.1c)."""

from __future__ import annotations

import pytest
from apps.accounts.forms import ProfileForm
from apps.accounts.models import User
from apps.accounts.views import ProfileView
from apps.core.roles import Role
from django.test import Client, RequestFactory
from django.urls import reverse

from tests.conftest import (
    TEST_CONFIRM_MISMATCH_PASSWORD,
    TEST_INVALID_PASSWORD_FOR_VALIDATION,
    TEST_LOGIN_PASSWORD,
    TEST_NEW_PASSWORD,
    TEST_ROTATED_PASSWORD,
    TEST_WRONG_LOGIN_PASSWORD,
    make_user,
)

ALL_ROLES = (
    Role.SUPER_ADMIN,
    Role.INSTITUTE_ADMIN,
    Role.SUB_ADMIN,
    Role.TEACHER,
    Role.STUDENT,
    Role.GUARDIAN,
)


@pytest.fixture
def client() -> Client:
    return Client()


def _login(client: Client, user: User) -> None:
    client.force_login(user)


@pytest.mark.django_db
@pytest.mark.parametrize("role", ALL_ROLES)
def test_profile_and_change_password_ok_for_every_role(
    client: Client, institute_a, role: str
) -> None:
    institute = None if role == Role.SUPER_ADMIN else institute_a
    user = make_user(
        email=f"{role}@example.com",
        role=role,
        institute=institute,
    )
    _login(client, user)
    assert client.get(reverse("accounts:profile")).status_code == 200
    assert client.get(reverse("accounts:change_password")).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_name",
    ["accounts:profile", "accounts:change_password"],
)
def test_anonymous_redirects_to_login(client: Client, url_name: str) -> None:
    response = client.get(reverse(url_name))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.django_db
def test_profile_get_renders_post_form_and_inputs(client: Client, institute_a) -> None:
    user = make_user(
        email="teacher@example.com",
        role=Role.TEACHER,
        institute=institute_a,
    )
    _login(client, user)
    response = client.get(reverse("accounts:profile"))
    html = response.content.decode()
    assert "<form" in html and 'method="post"' in html
    assert "csrfmiddlewaretoken" in html
    assert 'name="first_name"' in html
    assert "&lt;input" not in html


@pytest.mark.django_db
def test_profile_rejects_tampered_privileged_fields(
    client: Client, institute_a, institute_b
) -> None:
    user = make_user(
        email="teacher@example.com",
        role=Role.TEACHER,
        institute=institute_a,
        is_staff=False,
    )
    _login(client, user)
    response = client.post(
        reverse("accounts:profile"),
        {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "phone": "+1",
            "timezone": "UTC",
            "role": Role.INSTITUTE_ADMIN,
            "email": "hacker@example.com",
            "institute": str(institute_b.pk),
            "is_staff": "on",
        },
    )
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.role == Role.TEACHER
    assert user.email == "teacher@example.com"
    assert user.institute_id == institute_a.pk
    assert user.is_staff is False


@pytest.mark.django_db
def test_profile_rejects_invalid_timezone(client: Client, institute_a) -> None:
    user = make_user(
        email="teacher@example.com",
        role=Role.TEACHER,
        institute=institute_a,
    )
    _login(client, user)
    response = client.post(
        reverse("accounts:profile"),
        {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "phone": "",
            "timezone": "Not/A_Real_Zone",
        },
    )
    assert response.status_code == 200
    assert b"valid time zone" in response.content.lower()


@pytest.mark.django_db
def test_change_password_wrong_current_password(client: Client, institute_a) -> None:
    user = make_user(
        email="teacher@example.com",
        role=Role.TEACHER,
        institute=institute_a,
    )
    _login(client, user)
    response = client.post(
        reverse("accounts:change_password"),
        {
            "current_password": TEST_WRONG_LOGIN_PASSWORD,
            "new_password": TEST_NEW_PASSWORD,
            "confirm_password": TEST_NEW_PASSWORD,
        },
    )
    assert response.status_code == 200
    assert b"incorrect" in response.content.lower()


@pytest.mark.django_db
def test_change_password_confirm_must_match(client: Client, institute_a) -> None:
    user = make_user(
        email="teacher@example.com",
        role=Role.TEACHER,
        institute=institute_a,
    )
    _login(client, user)
    response = client.post(
        reverse("accounts:change_password"),
        {
            "current_password": TEST_LOGIN_PASSWORD,
            "new_password": TEST_NEW_PASSWORD,
            "confirm_password": TEST_CONFIRM_MISMATCH_PASSWORD,
        },
    )
    assert response.status_code == 200
    assert b"do not match" in response.content.lower()


@pytest.mark.django_db
def test_change_password_validate_password(client: Client, institute_a) -> None:
    user = make_user(
        email="teacher@example.com",
        role=Role.TEACHER,
        institute=institute_a,
    )
    _login(client, user)
    response = client.post(
        reverse("accounts:change_password"),
        {
            "current_password": TEST_LOGIN_PASSWORD,
            "new_password": TEST_INVALID_PASSWORD_FOR_VALIDATION,
            "confirm_password": TEST_INVALID_PASSWORD_FOR_VALIDATION,
        },
    )
    assert response.status_code == 200
    assert response.context is None or b"password" in response.content.lower()


@pytest.mark.django_db
def test_change_password_updates_password_and_keeps_session(
    client: Client, institute_a
) -> None:
    user = make_user(
        email="teacher@example.com",
        role=Role.TEACHER,
        institute=institute_a,
    )
    _login(client, user)
    response = client.post(
        reverse("accounts:change_password"),
        {
            "current_password": TEST_LOGIN_PASSWORD,
            "new_password": TEST_ROTATED_PASSWORD,
            "confirm_password": TEST_ROTATED_PASSWORD,
        },
    )
    assert response.status_code == 302
    assert client.get(reverse("accounts:profile")).status_code == 200
    user.refresh_from_db()
    assert user.check_password(TEST_ROTATED_PASSWORD)
    assert not user.check_password(TEST_LOGIN_PASSWORD)


@pytest.mark.django_db
def test_profile_post_requires_csrf(client: Client, institute_a) -> None:
    user = make_user(
        email="teacher@example.com",
        role=Role.TEACHER,
        institute=institute_a,
    )
    client = Client(enforce_csrf_checks=True)
    _login(client, user)
    response = client.post(
        reverse("accounts:profile"),
        {"first_name": "A", "last_name": "B", "phone": "", "timezone": ""},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_sub_admin_without_account_menu_gets_403(institute_a) -> None:
    user = make_user(
        email="sub@example.com",
        role=Role.SUB_ADMIN,
        institute=institute_a,
    )
    user.allowed_menus = ["dashboards"]
    request = RequestFactory().get(reverse("accounts:profile"))
    request.user = user
    request.institute = institute_a
    response = ProfileView.as_view()(request)
    assert response.status_code == 403


@pytest.mark.django_db
def test_profile_form_meta_excludes_role() -> None:
    assert "role" not in ProfileForm.Meta.fields


@pytest.mark.django_db
def test_mutation_profile_form_must_not_include_role_field() -> None:
    """Removing role from Meta.fields is required; adding it should fail this test."""
    assert set(ProfileForm.Meta.fields) <= {
        "first_name",
        "last_name",
        "phone",
        "timezone",
    }
