"""Flash messages show as toasts in every portal shell, once."""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from django.urls import reverse
from tests.conftest import make_user


@pytest.mark.django_db
def test_admin_shell_shows_success_message_once(client, institute_a) -> None:
    client.force_login(
        make_user(
            email="admin-a@example.com",
            role=Role.INSTITUTE_ADMIN,
            institute=institute_a,
        )
    )
    response = client.post(
        reverse("admin:campus"), {"name": "Institute A"}, follow=True
    )
    html = response.content.decode()

    assert "Campus profile updated." in html
    assert 'class="toast toast-success' in html
    assert (
        "Campus profile updated."
        not in client.get(reverse("admin:campus")).content.decode()
    )


@pytest.mark.django_db
def test_sidebar_shell_shows_messages(client, institute_a) -> None:
    client.force_login(make_user(email="super@example.com", role=Role.SUPER_ADMIN))
    url = reverse("super:institute_status", kwargs={"pk": institute_a.pk})

    response = client.post(url, {"action": "nope"}, follow=True)

    assert 'class="toast toast-error' in response.content.decode()
    assert "Unknown action." in response.content.decode()
