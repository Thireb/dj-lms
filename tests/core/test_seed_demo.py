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


def _demo_lectures():
    from apps.lectures.models import Lecture, RecurringSchedule

    institute = Institute.objects.get(name="Demo Institute")
    # unscoped: test assertion outside a tenant context.
    return (
        Lecture.unscoped.filter(institute=institute),
        RecurringSchedule.unscoped.filter(institute=institute),
    )


@pytest.mark.django_db
def test_seed_demo_adds_a_schedule_and_lectures_once(demo_env) -> None:
    call_command("seed_demo")
    lectures, schedules = _demo_lectures()
    first = lectures.count()
    call_command("seed_demo")

    teacher = TeacherProfile.unscoped.get(user__email="demo-teacher@example.com")
    assert schedules.count() == 1
    assert schedules.get().teacher == teacher
    assert lectures.filter(schedule__isnull=True).count() == 7
    assert lectures.filter(status="finished").count() == 3
    assert lectures.filter(status="not_held", started_at__isnull=True).count() == 1
    assert lectures.filter(status="live").count() == 1
    # Audit P3-3: the demo student sees them, so Join can be shown.
    from apps.core.tenancy import tenant_context
    from apps.lectures.models import Lecture

    student = User.objects.get(email="demo-student@example.com")
    guardian = User.objects.get(email="demo-guardian@example.com")
    with tenant_context(student.institute):
        visible = Lecture.objects.for_user(student)
        assert visible.filter(status="live").count() == 1
        assert visible.filter(status="scheduled").count() > 10
        assert Lecture.objects.for_user(guardian).count() == visible.count()
    assert first > 10  # Mon, Wed and Fri for the next 8 weeks
    assert lectures.count() == first


@pytest.mark.django_db
def test_reset_removes_demo_lectures(demo_env) -> None:
    call_command("seed_demo")
    call_command("seed_demo", "--reset")

    lectures, schedules = _demo_lectures()
    assert lectures.count() == schedules.count() == 0


@pytest.mark.django_db
def test_seed_demo_marks_two_lectures_once(demo_env) -> None:
    from apps.attendance.models import Attendance

    call_command("seed_demo")
    institute = Institute.objects.get(name="Demo Institute")
    # unscoped: test assertion outside a tenant context.
    marks = Attendance.unscoped.filter(institute=institute)
    first = marks.count()
    call_command("seed_demo")

    assert marks.count() == first > 0
    assert marks.values("lecture").distinct().count() == 2
    assert marks.filter(student__user__email="demo-student@example.com").count() == 2
    assert set(marks.values_list("status", flat=True)) == {
        "present",
        "late",
        "partial",
        "absent",
    }
    lectures, _ = _demo_lectures()
    newest = lectures.filter(status="finished").order_by("-starts_at").first()
    assert not marks.filter(lecture=newest).exists()
    call_command("seed_demo", "--reset")
    assert not marks.exists()


@pytest.mark.django_db
def test_seed_demo_adds_assignments_and_questions_once(demo_env) -> None:
    from apps.assessments.models import Assignment, Submission
    from apps.assessments.services import student_assignments
    from apps.core.tenancy import tenant_context

    call_command("seed_demo")
    call_command("seed_demo")
    institute = Institute.objects.get(name="Demo Institute")
    # unscoped: test assertion outside a tenant context.
    assignments = Assignment.unscoped.filter(institute=institute)
    answers = Submission.unscoped.filter(institute=institute)
    assert assignments.count() == 3
    assert answers.count() == 3
    assert answers.filter(marks__isnull=False).count() == 1
    student = StudentProfile.unscoped.get(user__email="demo-student@example.com")
    with tenant_context(institute):
        statuses = sorted(row.status for row in student_assignments(student))
    assert statuses == ["graded", "pending", "submitted"]
    from apps.assessments.models import Question

    # unscoped: test assertion outside a tenant context.
    questions = Question.unscoped.filter(institute=institute)
    assert questions.count() == 6
    assert questions.filter(kind="short").count() == 2
    assert {q.teacher.user.email for q in questions} == {"demo-teacher@example.com"}
    call_command("seed_demo", "--reset")
    assert not assignments.exists() and not answers.exists()
    assert not questions.all().exists()  # all(): a new query, not the cache
