"""Institute settings admin-only view."""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from django.test import Client
from django.urls import reverse
from tests.conftest import make_user


@pytest.mark.django_db
def test_settings_ok_for_institute_admin(client: Client, institute_a) -> None:
    user = make_user(
        email="admin@example.com",
        role=Role.INSTITUTE_ADMIN,
        institute=institute_a,
    )
    client.force_login(user)
    assert client.get(reverse("admin:institute_settings")).status_code == 200


@pytest.mark.django_db
def test_settings_forbidden_for_sub_admin(client: Client, institute_a) -> None:
    user = make_user(
        email="sub@example.com",
        role=Role.SUB_ADMIN,
        institute=institute_a,
    )
    user.allowed_menus = ["institute", "dashboards"]
    client.force_login(user)
    assert client.get(reverse("admin:institute_settings")).status_code == 403
