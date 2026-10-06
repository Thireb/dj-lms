"""Create institute flow (roadmap 1.3, audit G6/G8/G9)."""

from __future__ import annotations

import pytest
from apps.accounts.models import User
from apps.core.roles import Role
from apps.institutes.models import Institute, InstituteSettings
from django.test import Client
from django.urls import reverse
from tests.conftest import make_user


@pytest.fixture
def super_client(client: Client) -> Client:
    user = make_user(email="super@example.com", role=Role.SUPER_ADMIN, institute=None)
    client.force_login(user)
    return client


def _payload(basic_plan, **overrides) -> dict[str, str]:
    data = {
        "name": "New Academy",
        "plan": str(basic_plan.pk),
        "timezone": "Asia/Karachi",
        "currency_code": "USD",
        "admin_first_name": "Sana",
        "admin_last_name": "Example",
        "admin_email": "new-admin@example.com",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_create_institute_shows_link_once(super_client: Client, basic_plan) -> None:
    response = super_client.post(
        reverse("super:institute_create"), _payload(basic_plan)
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert "http://testserver/accounts/set-password/" in html
    assert "Copy link" in html
    institute = Institute.objects.get(name="New Academy")
    assert institute.currency_code == "USD"
    assert institute.currency_symbol == "$"
    assert InstituteSettings.unscoped.filter(institute=institute).count() == 1
    admin = User.objects.get(email="new-admin@example.com")
    assert admin.role == Role.INSTITUTE_ADMIN
    assert admin.institute == institute
    assert admin.first_name == "Sana"
    assert not admin.has_usable_password()


@pytest.mark.django_db
def test_set_password_token_never_stored_in_messages(
    super_client: Client, basic_plan
) -> None:
    response = super_client.post(
        reverse("super:institute_create"), _payload(basic_plan)
    )
    html = response.content.decode()
    token = html.split("/accounts/set-password/")[1].split("/")[0]
    assert token
    cookie_values = " ".join(c.value for c in super_client.cookies.values())
    assert token not in cookie_values
    follow_up = super_client.get(reverse("super:institute_list")).content.decode()
    assert token not in follow_up


@pytest.mark.django_db
def test_create_rejects_existing_email_case_insensitive(
    super_client: Client, basic_plan, institute_a
) -> None:
    make_user(email="taken@example.com", role=Role.TEACHER, institute=institute_a)
    response = super_client.post(
        reverse("super:institute_create"),
        _payload(basic_plan, admin_email="Taken@Example.com"),
    )
    assert response.status_code == 200
    assert "already exists" in response.content.decode()
    assert not Institute.objects.filter(name="New Academy").exists()


@pytest.mark.django_db
def test_create_rejects_invalid_timezone(super_client: Client, basic_plan) -> None:
    response = super_client.post(
        reverse("super:institute_create"),
        _payload(basic_plan, timezone="Mars/Base"),
    )
    assert response.status_code == 200
    assert "valid time zone" in response.content.decode()
    assert not Institute.objects.filter(name="New Academy").exists()
