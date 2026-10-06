"""Django admin site is gated to product super admins."""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from django.test import Client

from tests.conftest import make_user


@pytest.mark.django_db
def test_teacher_with_is_staff_gets_403_on_django_admin(
    client: Client, institute_a
) -> None:
    user = make_user(
        email="teacher-staff@example.com",
        role=Role.TEACHER,
        institute=institute_a,
        password="password123",
    )
    from apps.accounts.models import User

    User.objects.filter(pk=user.pk).update(is_staff=True)
    client.force_login(user)
    response = client.get("/django-admin/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_super_admin_can_reach_django_admin(client: Client) -> None:
    from apps.accounts.models import User

    user = User.objects.create_superuser(
        email="super@example.com",
        password="password123",
    )
    client.force_login(user)
    response = client.get("/django-admin/")
    assert response.status_code in {200, 302}
