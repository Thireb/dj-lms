"""Edit, activate and deactivate institutes (roadmap 1.3, audit G2/G7)."""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from django.test import Client
from django.urls import reverse
from tests.conftest import TEST_LOGIN_PASSWORD, make_user


@pytest.fixture
def super_client(client: Client) -> Client:
    user = make_user(email="super@example.com", role=Role.SUPER_ADMIN, institute=None)
    client.force_login(user)
    return client


def _status_url(institute) -> str:
    return reverse("super:institute_status", kwargs={"pk": institute.pk})


@pytest.mark.django_db
def test_edit_updates_name_plan_timezone_currency(
    super_client: Client, institute_a, basic_plan
) -> None:
    response = super_client.post(
        reverse("super:institute_edit", kwargs={"pk": institute_a.pk}),
        {
            "name": "Renamed",
            "plan": str(basic_plan.pk),
            "timezone": "Europe/London",
            "currency_code": "GBP",
        },
    )
    assert response.status_code == 302
    institute_a.refresh_from_db()
    assert institute_a.name == "Renamed"
    assert institute_a.timezone == "Europe/London"
    assert institute_a.currency_symbol == "£"
    assert institute_a.is_active is True


@pytest.mark.django_db
def test_edit_page_shows_confirm_dialog(super_client: Client, institute_a) -> None:
    html = super_client.get(
        reverse("super:institute_edit", kwargs={"pk": institute_a.pk})
    ).content.decode()
    assert f'action="{_status_url(institute_a)}"' in html
    assert "will not be able to sign in" in html
    assert 'name="action" value="deactivate"' in html


@pytest.mark.django_db
def test_deactivate_then_activate(super_client: Client, institute_a) -> None:
    assert super_client.post(_status_url(institute_a), {"action": "deactivate"})[
        "Location"
    ] == reverse("super:institute_edit", kwargs={"pk": institute_a.pk})
    institute_a.refresh_from_db()
    assert institute_a.is_active is False
    super_client.post(_status_url(institute_a), {"action": "activate"})
    institute_a.refresh_from_db()
    assert institute_a.is_active is True


@pytest.mark.django_db
def test_unknown_status_action_changes_nothing(
    super_client: Client, institute_a
) -> None:
    super_client.post(_status_url(institute_a), {"action": "delete"})
    institute_a.refresh_from_db()
    assert institute_a.is_active is True


@pytest.mark.django_db
def test_status_get_not_allowed(super_client: Client, institute_a) -> None:
    assert super_client.get(_status_url(institute_a)).status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize("role", [Role.INSTITUTE_ADMIN, Role.TEACHER])
def test_status_post_forbidden_for_other_roles(
    client: Client, institute_a, role: str
) -> None:
    user = make_user(email="x@example.com", role=role, institute=institute_a)
    client.force_login(user)
    response = client.post(_status_url(institute_a), {"action": "deactivate"})
    assert response.status_code == 403
    institute_a.refresh_from_db()
    assert institute_a.is_active is True


@pytest.mark.django_db
def test_deactivated_institute_users_cannot_sign_in(
    super_client: Client, institute_a
) -> None:
    make_user(email="teacher@example.com", role=Role.TEACHER, institute=institute_a)
    super_client.post(_status_url(institute_a), {"action": "deactivate"})
    response = Client().post(
        reverse("accounts:login"),
        {"email": "teacher@example.com", "password": TEST_LOGIN_PASSWORD},
    )
    assert response.status_code == 200
    assert "_auth_user_id" not in response.wsgi_request.session


@pytest.mark.django_db
def test_edit_unknown_pk_is_404_for_super_admin(super_client: Client) -> None:
    url = reverse("super:institute_edit", kwargs={"pk": 99999})
    assert super_client.get(url).status_code == 404


@pytest.mark.django_db
def test_edit_unknown_pk_redirects_anonymous(client: Client) -> None:
    url = reverse("super:institute_edit", kwargs={"pk": 99999})
    response = client.get(url)
    assert response.status_code == 302
    assert reverse("accounts:login") in response["Location"]


@pytest.mark.django_db
def test_edit_unknown_pk_is_403_for_teacher(client: Client, institute_a) -> None:
    client.force_login(
        make_user(email="t@example.com", role=Role.TEACHER, institute=institute_a)
    )
    url = reverse("super:institute_edit", kwargs={"pk": 99999})
    assert client.get(url).status_code == 403
