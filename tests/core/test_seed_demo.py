"""seed_demo management command (Phase 1 only)."""

from __future__ import annotations

import pytest
from apps.accounts.models import User
from apps.core.roles import Role
from apps.institutes.models import Institute
from django.core.management import call_command


@pytest.mark.django_db
def test_seed_demo_creates_demo_institute_and_role_users() -> None:
    call_command("seed_demo")
    institute = Institute.objects.get(name="Demo Institute")
    assert User.objects.filter(email="demo-admin@example.com", institute=institute)
    assert User.objects.filter(email="demo-super@example.com", role=Role.SUPER_ADMIN)
