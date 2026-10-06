"""Super Admin institute list (roadmap 1.3, audit G9)."""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from apps.institutes.models import Institute
from apps.superadmin.services import list_institutes
from django.test import Client
from django.urls import reverse
from tests.conftest import make_user


@pytest.fixture
def super_client(client: Client) -> Client:
    user = make_user(email="super@example.com", role=Role.SUPER_ADMIN, institute=None)
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_list_shows_columns(super_client: Client, institute_a, institute_b) -> None:
    make_user(email="t@example.com", role=Role.TEACHER, institute=institute_a)
    html = super_client.get(reverse("super:institute_list")).content.decode()
    assert "Institute A" in html
    assert "Institute B" in html
    assert "Active" in html
    assert "Users" in html
    assert "Created" in html
    assert 'name="q"' in html


@pytest.mark.django_db
def test_list_search_filters_by_name(
    super_client: Client, institute_a, institute_b
) -> None:
    filtered = super_client.get(reverse("super:institute_list"), {"q": "B"})
    text = filtered.content.decode()
    assert "Institute B" in text
    assert "Institute A" not in text
    assert 'value="B"' in text


@pytest.mark.django_db
def test_list_paginates_25_per_page(super_client: Client, basic_plan) -> None:
    for number in range(30):
        Institute.objects.create(name=f"Academy {number:02d}", plan=basic_plan)
    first = super_client.get(reverse("super:institute_list")).content.decode()
    assert "Academy 24" in first
    assert "Academy 25" not in first
    assert "Page 1 of 2" in first
    second = super_client.get(reverse("super:institute_list"), {"page": 2})
    assert "Academy 25" in second.content.decode()


@pytest.mark.django_db
def test_list_user_count(super_client: Client, institute_a) -> None:
    make_user(email="t1@example.com", role=Role.TEACHER, institute=institute_a)
    make_user(email="t2@example.com", role=Role.STUDENT, institute=institute_a)
    institute = list_institutes("Institute A").get()
    assert institute.user_count == 2


@pytest.mark.django_db
def test_institute_list_forbidden_for_institute_admin(
    client: Client, institute_a
) -> None:
    user = make_user(
        email="admin@example.com",
        role=Role.INSTITUTE_ADMIN,
        institute=institute_a,
    )
    client.force_login(user)
    assert client.get(reverse("super:institute_list")).status_code == 403


@pytest.mark.django_db
def test_super_shell_has_post_sign_out(super_client: Client) -> None:
    html = super_client.get(reverse("super:institute_list")).content.decode()
    assert f'action="{reverse("accounts:logout")}"' in html
    assert 'href="/accounts/logout/"' not in html
