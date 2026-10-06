"""createsuperuser sets product role super_admin (BACKLOG P2)."""

from __future__ import annotations

import pytest
from apps.accounts.models import User
from apps.core.roles import Role
from django.core.management import call_command


@pytest.mark.django_db
def test_createsuperuser_sets_super_admin_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_SUPERUSER_EMAIL", "dev@example.com")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "strong-pass-123")
    call_command("createsuperuser", interactive=False)

    user = User.objects.get(email="dev@example.com")
    assert user.role == Role.SUPER_ADMIN
    assert user.institute_id is None
    assert user.is_super_admin
