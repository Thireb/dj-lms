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
    html = response.content.decode()
    assert 'name="password"' in html
    assert 'type="password"' in html
    assert "<form" in html and 'method="post"' in html
    assert "csrfmiddlewaretoken" in html


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
    issued = create_set_password_token(user)
    url = reverse("accounts:set_password", kwargs={"token": issued.key})
    response = client.post(
        url,
        {"password": "newpass123", "confirm_password": "newpass123"},
    )
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.check_password("newpass123")
    issued.token.refresh_from_db()
    assert issued.token.used_at is not None


@pytest.mark.django_db
def test_set_password_expired_token(client: Client, institute_a) -> None:
    user = make_user(
        email="student@example.com",
        role=Role.STUDENT,
        institute=institute_a,
    )
    plaintext_key = SetPasswordToken.generate_key()
    SetPasswordToken.objects.create(
        user=user,
        key=SetPasswordToken.hash_key(plaintext_key),
        expires_at=timezone.now() - timedelta(hours=1),
    )
    url = reverse("accounts:set_password", kwargs={"token": plaintext_key})
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
    issued = create_set_password_token(user)
    issued.token.mark_used()
    url = reverse("accounts:set_password", kwargs={"token": issued.key})
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


@pytest.mark.django_db
def test_admin_top_nav_sign_out_is_post_form(client: Client, institute_a) -> None:
    user = make_user(
        email="admin@example.com",
        role=Role.INSTITUTE_ADMIN,
        institute=institute_a,
    )
    client.force_login(user)
    response = client.get(reverse("accounts:admin_home"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "top-nav" in html
    assert reverse("accounts:logout") in html
    logout_index = html.index(reverse("accounts:logout"))
    snippet = html[max(0, logout_index - 120) : logout_index + 120]
    assert 'method="post"' in snippet
    assert 'name="csrfmiddlewaretoken"' in snippet or "csrfmiddlewaretoken" in snippet


@pytest.mark.parametrize(
    ("role", "email", "home_name"),
    [
        (Role.INSTITUTE_ADMIN, "ia@example.com", "accounts:admin_home"),
        (Role.SUB_ADMIN, "sa@example.com", "accounts:admin_home"),
        (Role.TEACHER, "t@example.com", "accounts:teacher_home"),
        (Role.STUDENT, "s@example.com", "accounts:student_home"),
        (Role.GUARDIAN, "g@example.com", "accounts:guardian_home"),
    ],
)
@pytest.mark.django_db
def test_role_login_csrf_flow_reaches_portal_home(
    client: Client,
    institute_a,
    role: str,
    email: str,
    home_name: str,
) -> None:
    make_user(
        email=email,
        role=role,
        institute=institute_a,
        password="password123",
    )
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.get(reverse("accounts:login"))
    csrf = csrf_client.cookies["csrftoken"].value
    response = csrf_client.post(
        reverse("accounts:login"),
        {
            "email": email,
            "password": "password123",
            "csrfmiddlewaretoken": csrf,
        },
        follow=True,
    )
    assert response.status_code == 200
    assert response.request["PATH_INFO"] == reverse(home_name)


@pytest.mark.django_db
def test_login_rejects_inactive_institute(client: Client, institute_a) -> None:
    institute_a.is_active = False
    institute_a.save(update_fields=["is_active"])
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
        },
    )
    assert response.status_code == 200
    assert not response.wsgi_request.user.is_authenticated
    assert b"not active" in response.content.lower()


@pytest.mark.django_db
def test_login_active_institute_still_works(client: Client, institute_a) -> None:
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
        },
    )
    assert response.status_code == 302
    assert response.wsgi_request.user.is_authenticated


@pytest.mark.django_db
def test_super_admin_login_csrf_flow(client: Client) -> None:
    from apps.accounts.models import User

    User.objects.create_superuser(
        email="super@example.com",
        password="password123",
    )
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.get(reverse("accounts:login"))
    csrf = csrf_client.cookies["csrftoken"].value
    response = csrf_client.post(
        reverse("accounts:login"),
        {
            "email": "super@example.com",
            "password": "password123",
            "csrfmiddlewaretoken": csrf,
        },
        follow=True,
    )
    assert response.status_code == 200
    assert response.request["PATH_INFO"] == reverse("accounts:super_admin_home")
