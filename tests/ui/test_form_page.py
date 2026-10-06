"""FormPage POST handling, CSRF, and TenantModelForm institute wiring."""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from django.test import Client
from django.urls import reverse
from tests.conftest import make_user
from tests.testapp.models import TenantProbe


@pytest.fixture
def client() -> Client:
    return Client()


@pytest.mark.django_db
def test_form_page_get_renders_unbound_form(client: Client, institute_a) -> None:
    user = make_user(
        email="teacher@example.com",
        role=Role.TEACHER,
        institute=institute_a,
    )
    client.force_login(user)
    url = reverse("test_tenant_probe_form")
    response = client.get(url)
    assert response.status_code == 200
    html = response.content.decode()
    assert "<form" in html and 'method="post"' in html
    assert "csrfmiddlewaretoken" in html


@pytest.mark.django_db
def test_form_page_post_saves_in_user_institute(client: Client, institute_a) -> None:
    user = make_user(
        email="teacher@example.com",
        role=Role.TEACHER,
        institute=institute_a,
    )
    client.force_login(user)
    url = reverse("test_tenant_probe_form")
    response = client.post(url, {"label": "from-form-page"})
    assert response.status_code == 302
    probe = TenantProbe.objects.for_user(user).get()
    assert probe.label == "from-form-page"
    assert probe.institute_id == institute_a.pk


@pytest.mark.django_db
def test_form_page_post_without_csrf_returns_403(client: Client, institute_a) -> None:
    user = make_user(
        email="teacher@example.com",
        role=Role.TEACHER,
        institute=institute_a,
    )
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    url = reverse("test_tenant_probe_form")
    response = client.post(url, {"label": "nope"})
    assert response.status_code == 403


@pytest.mark.django_db
def test_form_page_invalid_post_rerendered_with_errors(
    client: Client, institute_a
) -> None:
    user = make_user(
        email="teacher@example.com",
        role=Role.TEACHER,
        institute=institute_a,
    )
    client.force_login(user)
    url = reverse("test_tenant_probe_form")
    response = client.post(url, {})
    assert response.status_code == 200
    html = response.content.decode()
    assert "This field is required" in html or "Label is required" in html
    assert TenantProbe.objects.for_user(user).count() == 0
