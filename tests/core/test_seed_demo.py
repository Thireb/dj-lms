"""seed_demo management command (Phase 1 only)."""

from __future__ import annotations

import pytest
from apps.accounts.models import User
from apps.core.features import PLAN_CODE_PREMIUM
from apps.core.roles import Role
from apps.institutes.models import Institute
from django.core.management import call_command
from django.core.management.base import CommandError

DEMO_PASSWORD = "fake-demo-password-for-tests"


@pytest.fixture
def demo_env(monkeypatch, settings):
    settings.DEBUG = True
    monkeypatch.setenv("SEED_DEMO_PASSWORD", DEMO_PASSWORD)


@pytest.mark.django_db
def test_seed_demo_creates_demo_institute_and_role_users(demo_env) -> None:
    call_command("seed_demo")
    institute = Institute.objects.get(name="Demo Institute")
    assert institute.plan.code == PLAN_CODE_PREMIUM
    admin = User.objects.get(email="demo-admin@example.com")
    assert admin.institute == institute
    assert admin.check_password(DEMO_PASSWORD)
    assert User.objects.filter(email="demo-super@example.com", role=Role.SUPER_ADMIN)


@pytest.mark.django_db
def test_seed_demo_twice_creates_no_duplicates(demo_env) -> None:
    call_command("seed_demo")
    call_command("seed_demo")
    assert Institute.objects.filter(name="Demo Institute").count() == 1
    assert User.objects.filter(email__startswith="demo-").count() == 6


@pytest.mark.django_db
def test_seed_demo_refuses_when_debug_off(monkeypatch, settings) -> None:
    settings.DEBUG = False
    monkeypatch.setenv("SEED_DEMO_PASSWORD", DEMO_PASSWORD)
    with pytest.raises(CommandError, match="DEBUG"):
        call_command("seed_demo")
    assert not User.objects.filter(email__startswith="demo-").exists()


@pytest.mark.django_db
def test_seed_demo_requires_password_env(monkeypatch, settings) -> None:
    settings.DEBUG = True
    monkeypatch.delenv("SEED_DEMO_PASSWORD", raising=False)
    with pytest.raises(CommandError, match="SEED_DEMO_PASSWORD"):
        call_command("seed_demo")


@pytest.mark.django_db
def test_seed_demo_reset_removes_users_and_deactivates_institute(demo_env) -> None:
    call_command("seed_demo")
    call_command("seed_demo", "--reset")
    assert not User.objects.filter(email__startswith="demo-").exists()
    assert not Institute.objects.get(name="Demo Institute").is_active


@pytest.mark.django_db
def test_seed_demo_reset_refuses_when_debug_off(demo_env, settings) -> None:
    call_command("seed_demo")
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DEBUG"):
        call_command("seed_demo", "--reset")
    assert User.objects.filter(email__startswith="demo-").count() == 6
