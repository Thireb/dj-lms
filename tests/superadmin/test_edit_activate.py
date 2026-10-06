"""Edit and deactivate institutes."""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from django.test import Client
from django.urls import reverse
from tests.conftest import make_user


@pytest.mark.django_db
def test_deactivate_institute(client: Client, institute_a, basic_plan) -> None:
    user = make_user(email="super@example.com", role=Role.SUPER_ADMIN, institute=None)
    client.force_login(user)
    response = client.post(
        reverse("super:institute_edit", kwargs={"pk": institute_a.pk}),
        {
            "name": institute_a.name,
            "plan": str(basic_plan.pk),
            "is_active": "",
        },
    )
    assert response.status_code == 302
    institute_a.refresh_from_db()
    assert institute_a.is_active is False
