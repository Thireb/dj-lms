"""Create institute flow."""

from __future__ import annotations

import pytest
from apps.accounts.models import User
from apps.core.roles import Role
from apps.institutes.models import Institute
from django.test import Client
from django.urls import reverse
from tests.conftest import make_user


@pytest.mark.django_db
def test_create_institute_shows_set_password_link(client: Client, basic_plan) -> None:
    user = make_user(email="super@example.com", role=Role.SUPER_ADMIN, institute=None)
    client.force_login(user)
    response = client.post(
        reverse("super:institute_create"),
        {
            "name": "New Academy",
            "plan": str(basic_plan.pk),
            "admin_email": "new-admin@example.com",
            "timezone": "Asia/Karachi",
        },
    )
    assert response.status_code == 302
    assert Institute.objects.filter(name="New Academy").exists()
    admin = User.objects.get(email="new-admin@example.com")
    assert admin.role == Role.INSTITUTE_ADMIN
    assert admin.institute.name == "New Academy"
