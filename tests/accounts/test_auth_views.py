"""Login, logout, set-password, and forgot-password flows."""

from __future__ import annotations

from datetime import timedelta

import pytest
from apps.accounts.models import SetPasswordToken
from apps.accounts.services import create_set_password_token
from apps.core.roles import Role
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from tests.conftest import make_user


@pytest.fixture
def client() -> Client:
    return Client()


@pytest.mark.django_db
def test_login_page_renders_for_anonymous(client: Client) -> None:
    response = client.get(reverse("accounts:login"))
    assert response.status_code == 200
    assert b"Sign in" in response.content
    assert b"Remember me" in response.content
    assert b"Show" in response.content


@pytest.mark.django_db
def test_login_success_redirects_teacher(client: Client, institute_a) -> None:
    make_user(
        email="teacher@example.com",
        role=Role.TEACHER,
        institute=institute_a,
        password="password123",
    )
    response = client.post(
        reverse("accounts:login"),
        {
            "email": "teacher@example.com",
            "password": "password123",
            "remember_me": True,
        },
    )
    assert response.status_code == 302
    assert response.wsgi_request.user.is_authenticated


@pytest.mark.django_db
def test_login_invalid_credentials(client: Client) -> None:
    response = client.post(
        reverse("accounts:login"),
        {"email": "nope@example.com", "password": "wrong"},
    )
    assert response.status_code == 200
    assert b"incorrect" in response.content.lower()


@pytest.mark.django_db
def test_login_requires_csrf(client: Client) -> None:
    client = Client(enforce_csrf_checks=True)
    response = client.post(
        reverse("accounts:login"),
        {"email": "a@b.com", "password": "x"},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_logout_post_only(client: Client, institute_a) -> None:
    user = make_user(
        email="teacher@example.com",
        role=Role.TEACHER,
        institute=institute_a,
        password="password123",
    )
    client.force_login(user)
    assert client.get(reverse("accounts:logout")).status_code == 405
    response = client.post(reverse("accounts:logout"))
    assert response.status_code == 302
    assert response.url == reverse("accounts:login")


@pytest.mark.django_db
def test_logout_post_requires_csrf(client: Client, institute_a) -> None:
    user = make_user(
        email="teacher@example.com",
        role=Role.TEACHER,
        institute=institute_a,
    )
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    assert client.post(reverse("accounts:logout")).status_code == 403


@pytest.mark.django_db
def test_forgot_password_shows_admin_message(client: Client) -> None:
    response = client.get(reverse("accounts:forgot_password"))
    assert response.status_code == 200
    assert b"Contact your institute admin" in response.content


@pytest.mark.django_db
def test_set_password_happy_path(client: Client, institute_a) -> None:
    user = make_user(
        email="student@example.com",
        role=Role.STUDENT,
        institute=institute_a,
        password="unset",
    )
    token = create_set_password_token(user)
    url = reverse("accounts:set_password", kwargs={"token": token.key})
    response = client.post(
        url,
        {"password": "newpass123", "confirm_password": "newpass123"},
    )
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.check_password("newpass123")
    token.refresh_from_db()
    assert token.used_at is not None


@pytest.mark.django_db
def test_set_password_expired_token(client: Client, institute_a) -> None:
    user = make_user(
        email="student@example.com",
        role=Role.STUDENT,
        institute=institute_a,
    )
    token = SetPasswordToken.objects.create(
        user=user,
        key=SetPasswordToken.generate_key(),
        expires_at=timezone.now() - timedelta(hours=1),
    )
    url = reverse("accounts:set_password", kwargs={"token": token.key})
    response = client.get(url)
    assert response.status_code == 200
    assert b"expired" in response.content.lower()


@pytest.mark.django_db
def test_set_password_used_token(client: Client, institute_a) -> None:
    user = make_user(
        email="student@example.com",
        role=Role.STUDENT,
        institute=institute_a,
    )
    token = create_set_password_token(user)
    token.mark_used()
    url = reverse("accounts:set_password", kwargs={"token": token.key})
    response = client.get(url)
    assert response.status_code == 200
    assert b"already used" in response.content.lower()


@pytest.mark.django_db
def test_anonymous_portal_page_redirects_to_login(client: Client, institute_a) -> None:
    path = "/test/pages/teacher-dashboard/"
    response = client.get(path)
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url
    assert f"next={path}" in response.url


@pytest.mark.django_db
def test_teacher_dashboard_still_forbidden_for_student(
    client: Client, institute_a
) -> None:
    user = make_user(
        email="student@example.com",
        role=Role.STUDENT,
        institute=institute_a,
    )
    client.force_login(user)
    response = client.get("/test/pages/teacher-dashboard/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_sign_out_renders_post_form(client: Client, institute_a) -> None:
    user = make_user(
        email="teacher@example.com",
        role=Role.TEACHER,
        institute=institute_a,
    )
    client.force_login(user)
    response = client.get("/test/pages/teacher-dashboard/")
    assert response.status_code == 200
    html = response.content.decode()
    assert 'method="post"' in html
    assert reverse("accounts:logout") in html
    assert "csrfmiddlewaretoken" in html
