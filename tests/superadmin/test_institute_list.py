"""Super Admin institute list."""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from django.test import Client
from django.urls import reverse
from tests.conftest import make_user


@pytest.mark.django_db
def test_institute_list_for_super_admin(client: Client) -> None:
    user = make_user(email="super@example.com", role=Role.SUPER_ADMIN, institute=None)
    client.force_login(user)
    assert client.get(reverse("super:institute_list")).status_code == 200


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
