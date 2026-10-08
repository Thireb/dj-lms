"""seed_demo management command (Phase 1 sign-ins and the 2.8 SPEC 10 volume)."""

from __future__ import annotations

import pytest
from apps.academics.models import Batch, ClassLabel, StudentBatchSubject, Subject
from apps.accounts.models import User
from apps.core.features import PLAN_CODE_PREMIUM
from apps.core.roles import Role
from apps.institutes.models import Institute, Plan
from apps.people.models import (
    GuardianProfile,
    GuardianStudentLink,
    PortalAccessRule,
    StudentProfile,
    TeacherProfile,
)
from django.core.management import call_command
from django.core.management.base import CommandError

DEMO_PASSWORD = "fake-demo-password-for-tests"
DEMO_USER_COUNT = 3 + 5 + 52 + 20  # staff sign-ins, teachers, students, guardians


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
    assert User.objects.filter(email__startswith="demo-").count() == DEMO_USER_COUNT


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
    assert User.objects.filter(email__startswith="demo-").count() == DEMO_USER_COUNT


def _demo_counts() -> dict:
    institute = Institute.objects.get(name="Demo Institute")
    # unscoped: test assertions outside a tenant context.
    students = StudentProfile.unscoped.filter(institute=institute)
    return {
        "classes": ClassLabel.unscoped.filter(institute=institute).count(),
        "batches": Batch.unscoped.filter(institute=institute).count(),
        "subjects": Subject.unscoped.filter(institute=institute).count(),
        "teachers": TeacherProfile.unscoped.filter(institute=institute).count(),
        "students": students.count(),
        "active": students.filter(status="active").count(),
        "guardians": GuardianProfile.unscoped.filter(institute=institute).count(),
        "blocked": PortalAccessRule.unscoped.filter(blocked=True).count(),
        "exempt": PortalAccessRule.unscoped.filter(exempt=True).count(),
    }


@pytest.mark.django_db
def test_seed_demo_builds_the_spec_10_volume(demo_env) -> None:
    call_command("seed_demo")

    assert _demo_counts() == {
        "classes": 3,
        "batches": 4,
        "subjects": 6,
        "teachers": 5,
        "students": 52,
        "active": 30,
        "guardians": 20,
        "blocked": 1,
        "exempt": 1,
    }


@pytest.mark.django_db
def test_demo_people_follow_the_app_rules(demo_env) -> None:
    call_command("seed_demo")

    # unscoped: test assertions outside a tenant context.
    demo_student = StudentProfile.unscoped.get(user__email="demo-student@example.com")
    demo_guardian = GuardianProfile.unscoped.get(
        user__email="demo-guardian@example.com"
    )
    children = GuardianStudentLink.unscoped.filter(guardian=demo_guardian)
    assert demo_student.student_code == "STU-001"
    assert children.count() == 2
    assert StudentBatchSubject.unscoped.filter(student=demo_student).exists()
    assert (
        TeacherProfile.unscoped.get(user__email="demo-teacher@example.com").teacher_code
        == "TCH-001"
    )
    inactive = User.objects.get(email="demo-student-52@example.com")
    assert inactive.is_active is False
    assert User.objects.get(email="demo-student@example.com").check_password(
        DEMO_PASSWORD
    )
    for student in StudentProfile.unscoped.all():
        assert GuardianStudentLink.unscoped.filter(student=student).exists()


@pytest.mark.django_db
def test_seed_demo_twice_keeps_the_same_volume(demo_env) -> None:
    call_command("seed_demo")
    first = _demo_counts()
    call_command("seed_demo")

    assert _demo_counts() == first


@pytest.mark.django_db
def test_reset_removes_all_demo_people_and_seed_works_again(demo_env) -> None:
    call_command("seed_demo")
    call_command("seed_demo", "--reset")

    assert set(_demo_counts().values()) == {0}
    call_command("seed_demo")
    assert _demo_counts()["students"] == 52


@pytest.mark.django_db
def test_seed_takes_over_phase_1_users_without_profiles(demo_env) -> None:
    institute = Institute.objects.create(
        name="Demo Institute", plan=Plan.objects.get(code=PLAN_CODE_PREMIUM)
    )
    User.objects.create_user(
        email="demo-student@example.com",
        password="old-fake-pass-1x",
        role=Role.STUDENT,
        institute=institute,
    )

    call_command("seed_demo")

    # unscoped: test assertion outside a tenant context.
    assert StudentProfile.unscoped.filter(
        user__email="demo-student@example.com"
    ).exists()
