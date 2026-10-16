"""Walk every product URL and check the role gate (roadmap 1.4, audit G3).

For each named URL in ``config.urls`` that is not public:
- the view is a ``PortalPageView`` with a non-empty ``allowed_roles``;
- anonymous users are redirected to login;
- every role not in ``allowed_roles`` gets 403;
- at least one allowed role gets through (200, or 405 for POST-only views).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time, timedelta
from typing import Any

import pytest
from apps.academics.models import Batch, ClassLabel, Subject
from apps.academics.services import (
    set_student_batch_subjects,
    set_teacher_batch_subjects,
)
from apps.accounts.models import User
from apps.assessments.models import (
    Assignment,
    Question,
    QuestionKind,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    Submission,
)
from apps.core.features import ALL_FEATURE_KEYS
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.finance.models import Challan, FeePlan
from apps.institutes.models import Plan
from apps.lectures.models import Lecture, LectureStatus, RecurringSchedule
from apps.messaging.models import Draft, Thread, ThreadMember
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.people.models import StudentProfile, TeacherProfile
from apps.people.services import create_student_profile, create_teacher_profile
from apps.ui.views.pages import PortalPageView
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver, reverse
from django.utils import timezone

from tests.conftest import make_user

PUBLIC_ALLOWLIST = {
    "accounts:login",
    "accounts:logout",
    "accounts:forgot_password",
    "accounts:set_password",
    "dev_components",
    "health",  # uptime check (S13), no data
    "root",
}
SKIPPED_NAMESPACES = {"developer"}  # /django-admin/, gated by middleware tests.
# Parts of the bell and the menu's unread badge that HTMX loads: a signed-out
# user gets an empty 204, so HTMX never shows the sign-in page in them
# (roadmap 6.1 and 6.3).
EMPTY_FOR_ANONYMOUS = {
    "notifications:count",
    "notifications:panel",
    *(
        f"{portal}:message_unread"
        for portal in ("admin", "teacher", "student", "guardian")
    ),
}


@dataclass(frozen=True)
class Route:
    name: str
    view_class: Any
    kwarg_names: tuple[str, ...]


def _walk(patterns, namespace: str = "") -> list[Route]:
    routes: list[Route] = []
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            child = pattern.namespace or ""
            if child in SKIPPED_NAMESPACES:
                continue
            prefix = f"{namespace}:{child}" if namespace and child else child
            routes += _walk(pattern.url_patterns, prefix or namespace)
        elif isinstance(pattern, URLPattern) and pattern.name:
            name = f"{namespace}:{pattern.name}" if namespace else pattern.name
            routes.append(
                Route(
                    name=name,
                    view_class=getattr(pattern.callback, "view_class", None),
                    kwarg_names=tuple(pattern.pattern.converters),
                )
            )
    return routes


PRODUCT_ROUTES = [
    route
    for route in _walk(get_resolver("config.urls").url_patterns)
    if route.name not in PUBLIC_ALLOWLIST
]


def test_walker_finds_the_product_urls() -> None:
    names = {route.name for route in PRODUCT_ROUTES}
    assert {
        "admin:home",
        "admin:campus",
        "admin:institute_settings",
        "super:institute_list",
        "super:institute_edit",
        "super:institute_status",
        "accounts:profile",
        "admin:batch_list",
        "admin:batch_edit",
        "admin:teacher_list",
        "admin:teacher_edit",
        "admin:student_list",
        "admin:student_edit",
    } <= names


def test_every_route_with_a_pk_has_an_object() -> None:
    # A pk route without a real row would pass the walker with a 404.
    for route in PRODUCT_ROUTES:
        if route.kwarg_names and route.name.startswith("admin:"):
            assert route.name in ROUTE_OBJECTS, route.name


@pytest.mark.parametrize("route", PRODUCT_ROUTES, ids=lambda r: r.name)
def test_every_product_view_declares_roles(route: Route) -> None:
    assert route.view_class is not None, f"{route.name} is a function view"
    assert issubclass(route.view_class, PortalPageView), route.name
    assert route.view_class.allowed_roles, f"{route.name} has no allowed_roles"


# Routes whose pk is not an institute: build a row in the institute instead.
def _name_row(model):
    def build(institute) -> int:
        # unscoped: test setup outside a tenant context.
        row, _ = model.unscoped.get_or_create(institute=institute, name="Walker")
        return row.pk

    return build


def _teacher(institute) -> int:
    # unscoped: test setup outside a tenant context.
    existing = TeacherProfile.unscoped.filter(institute=institute).first()
    if existing is not None:
        return existing.pk
    user = make_user(
        email="teacher-row-walker@example.com",
        role=Role.TEACHER,
        institute=institute,
    )
    with tenant_context(institute):
        return create_teacher_profile(user).pk


def _student(institute) -> int:
    # unscoped: test setup outside a tenant context.
    existing = StudentProfile.unscoped.filter(institute=institute).first()
    if existing is not None:
        return existing.pk
    user = make_user(
        email="student-row-walker@example.com",
        role=Role.STUDENT,
        institute=institute,
    )
    with tenant_context(institute):
        return create_student_profile(user, guardian_phone="0300-0000000").pk


def _lecture(institute) -> int:
    # The teacher portal opens only the walker teacher's own lectures.
    # unscoped: test setup outside a tenant context.
    walker = TeacherProfile.unscoped.filter(
        institute=institute, user__email=f"{Role.TEACHER}-walker@example.com"
    ).first()
    teacher = walker or TeacherProfile.unscoped.get(pk=_teacher(institute))
    batch = Batch.unscoped.get(pk=_name_row(Batch)(institute))
    subject = Subject.unscoped.get(pk=_name_row(Subject)(institute))
    with tenant_context(institute):
        set_teacher_batch_subjects(teacher, {batch: [subject]})
        lecture = Lecture(
            institute=institute,
            title="Walker",
            teacher=teacher,
            batch=batch,
            starts_at=timezone.now() + timedelta(days=1),
            duration_minutes=60,
            meeting_url="https://meet.example.com/walker",
        )
        lecture.save()
        lecture.subjects.set([subject])
    return lecture.pk


def _finished_lecture(institute) -> int:
    """Attendance opens only for a finished lecture."""
    pk = _lecture(institute)
    # unscoped: test setup outside a tenant context.
    Lecture.unscoped.filter(pk=pk).update(
        starts_at=timezone.now() - timedelta(days=1), status=LectureStatus.FINISHED
    )
    return pk


def _schedule(institute) -> int:
    lecture = Lecture.unscoped.get(pk=_lecture(institute))
    with tenant_context(institute):
        schedule = RecurringSchedule(
            institute=institute,
            title="Walker",
            teacher=lecture.teacher,
            batch=lecture.batch,
            weekdays=[0],
            start_time=time(10, 0),
            time_zone="Asia/Karachi",
            duration_minutes=60,
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=30),
            meeting_url="https://meet.example.com/walker",
        )
        schedule.save()
    return schedule.pk


def _assignment(institute) -> int:
    """An open assignment of the walker teacher. The walker student (when
    the walk made one) gets a profile in its batch and subject."""
    # unscoped: test setup outside a tenant context.
    lecture = Lecture.unscoped.get(pk=_lecture(institute))
    subject = Subject.unscoped.get(pk=_name_row(Subject)(institute))
    walker = User.objects.filter(email=f"{Role.STUDENT}-walker@example.com").first()
    with tenant_context(institute):
        assignment = Assignment.objects.create(
            institute=institute,
            title="Walker",
            instructions="Walk.",
            teacher=lecture.teacher,
            batch=lecture.batch,
            subject=subject,
            total_marks=10,
            due_at=timezone.now() + timedelta(days=1),
        )
        if walker is not None and not StudentProfile.objects.filter(user=walker):
            student = create_student_profile(walker, guardian_phone="0300-0000000")
            set_student_batch_subjects(student, {lecture.batch: [subject]})
    return assignment.pk


def _answer(institute) -> dict[str, int]:
    """The grade page has two pks: the assignment and one answer to it."""
    # unscoped: test setup outside a tenant context.
    assignment = Assignment.unscoped.get(pk=_assignment(institute))
    student = StudentProfile.unscoped.get(pk=_student(institute))
    with tenant_context(institute):
        answer = Submission.objects.create(
            institute=institute,
            assignment=assignment,
            student=student,
            answer="Walker answer.",
            submitted_at=timezone.now(),
        )
    return {"pk": assignment.pk, "submission_pk": answer.pk}


def _question(institute) -> int:
    """A short answer question in the walker teacher's bank."""
    # unscoped: test setup outside a tenant context.
    lecture = Lecture.unscoped.get(pk=_lecture(institute))
    subject = Subject.unscoped.get(pk=_name_row(Subject)(institute))
    with tenant_context(institute):
        question = Question.objects.create(
            institute=institute,
            teacher=lecture.teacher,
            subject=subject,
            kind=QuestionKind.SHORT,
            text="Walker?",
            marks=1,
        )
    return question.pk


def _quiz(institute) -> int:
    """A draft quiz of the walker teacher, opening tomorrow."""
    question = Question.unscoped.get(pk=_question(institute))  # unscoped: setup
    lecture = Lecture.unscoped.get(pk=_lecture(institute))  # unscoped: setup
    with tenant_context(institute):
        quiz = Quiz.objects.create(
            institute=institute,
            title="Walker",
            teacher=question.teacher,
            batch=lecture.batch,
            subject=question.subject,
            opens_at=timezone.now() + timedelta(days=1),
            duration_minutes=30,
        )
    return quiz.pk


def _quiz_item(institute) -> dict[str, int]:
    """The remove page has two pks: the quiz and one of its questions."""
    quiz = Quiz.unscoped.get(pk=_quiz(institute))  # unscoped: test setup
    question = Question.unscoped.get(pk=_question(institute))  # unscoped: setup
    with tenant_context(institute):
        item = QuizQuestion.objects.create(
            institute=institute, quiz=quiz, question=question, position=1
        )
    return {"pk": quiz.pk, "item_pk": item.pk}


def _live_quiz(institute) -> int:
    """A published quiz that opened a minute ago, in the batch and subject
    of the walker student (made by ``_assignment``)."""
    # unscoped: test setup outside a tenant context.
    assignment = Assignment.unscoped.get(pk=_assignment(institute))
    quiz = Quiz.unscoped.get(pk=_quiz(institute))
    Quiz.unscoped.filter(pk=quiz.pk).update(
        batch=assignment.batch,
        subject=assignment.subject,
        is_published=True,
        opens_at=timezone.now() - timedelta(minutes=1),
    )
    return quiz.pk


def _attempt(institute) -> int:
    """The attempt page needs an open attempt of the walker student."""
    pk = _live_quiz(institute)
    walker = User.objects.filter(email=f"{Role.STUDENT}-walker@example.com").first()
    # unscoped: test setup outside a tenant context.
    student = StudentProfile.unscoped.filter(user=walker).first()
    if student is not None:
        now = timezone.now()
        with tenant_context(institute):
            QuizAttempt.objects.get_or_create(
                institute=institute,
                quiz_id=pk,
                student=student,
                defaults={
                    "started_at": now,
                    "deadline": now + timedelta(minutes=30),
                    "question_order": [0],  # an attempt always has questions
                },
            )
    return pk


def _quiz_attempt(institute) -> dict[str, int]:
    """The teacher's attempt page has two pks: the quiz and an attempt."""
    pk = _live_quiz(institute)
    # unscoped: test setup outside a tenant context.
    student = StudentProfile.unscoped.get(pk=_student(institute))
    now = timezone.now()
    with tenant_context(institute):
        attempt, _ = QuizAttempt.objects.get_or_create(
            institute=institute,
            quiz_id=pk,
            student=student,
            defaults={
                "started_at": now,
                "deadline": now + timedelta(minutes=30),
                "question_order": [0],
            },
        )
    return {"pk": pk, "attempt_pk": attempt.pk}


def _notification(institute) -> int:
    email = "notified-walker@example.com"
    user = User.objects.filter(email=email).first() or make_user(
        email=email, role=Role.TEACHER, institute=institute
    )
    with tenant_context(institute):
        notify([user], "new_message", "Walker note.")
    # unscoped: test setup outside a tenant context.
    return Notification.unscoped.filter(user=user).first().pk


def _thread(institute) -> int:
    """A thread with every user of the institute in it, so each walker role
    may open it (the role's user exists before the URL is built)."""
    # unscoped: test setup outside a tenant context.
    thread = Thread.unscoped.filter(institute=institute, subject="Walker").first()
    now = timezone.now()
    if thread is None:
        thread = Thread.unscoped.create(
            institute=institute, subject="Walker", created_at=now, last_message_at=now
        )
    for user in User.objects.filter(institute=institute):
        ThreadMember.unscoped.get_or_create(
            institute=institute, thread=thread, user=user
        )
    return thread.pk


def _challan(institute) -> int:
    # unscoped: test setup outside a tenant context.
    existing = Challan.unscoped.filter(institute=institute).first()
    if existing is not None:
        return existing.pk
    today = timezone.localdate()
    return Challan.unscoped.create(
        institute=institute,
        student_id=_student(institute),
        number="CH-WALKER-0001",
        month=today.replace(day=1),
        issue_date=today,
        due_date=today,
        amount=1000,
    ).pk


def _fee_plan(institute) -> int:
    # unscoped: test setup outside a tenant context.
    plan, _ = FeePlan.unscoped.get_or_create(
        institute=institute, name="Walker", defaults={"amount": 1000}
    )
    return plan.pk


def _draft(institute) -> int:
    email = "drafter-walker@example.com"
    owner = User.objects.filter(email=email).first() or make_user(
        email=email, role=Role.TEACHER, institute=institute
    )
    # unscoped: test setup outside a tenant context.
    return Draft.unscoped.create(
        institute=institute, owner=owner, updated_at=timezone.now()
    ).pk


ROUTE_OBJECTS = {
    **{
        f"admin:{prefix}_{action}": _name_row(model)
        for prefix, model in (
            ("class", ClassLabel),
            ("batch", Batch),
            ("subject", Subject),
        )
        for action in ("edit", "status")
    },
    "admin:teacher_edit": _teacher,
    "admin:teacher_status": _teacher,
    "admin:student_edit": _student,
    "admin:student_status": _student,
    "admin:portal_access_action": _student,
    "admin:lecture_edit": _lecture,
    "teacher:lecture_edit": _lecture,
    "admin:lecture_detail": _lecture,
    "admin:quiz_detail": _quiz,
    "admin:lecture_cancel": _lecture,
    "teacher:lecture_detail": _lecture,
    "teacher:lecture_start": _lecture,
    "teacher:lecture_end": _lecture,
    "student:lecture_join": _lecture,
    "teacher:lecture_attendance": _finished_lecture,
    "teacher:assignment_detail": _assignment,
    "teacher:assignment_edit": _assignment,
    "teacher:assignment_grade": _answer,
    "student:assignment_detail": _assignment,
    "teacher:question_edit": _question,
    "teacher:question_delete": _question,
    **{
        f"teacher:quiz_{action}": _quiz
        for action in ("detail", "edit", "add_questions", "publish", "unpublish")
    },
    "teacher:quiz_remove_question": _quiz_item,
    "teacher:quiz_attempt": _quiz_attempt,
    "student:quiz_detail": _live_quiz,
    "student:quiz_start": _live_quiz,
    "student:quiz_event": _live_quiz,
    "student:quiz_attempt": _attempt,
    "notifications:open": _notification,
    **{f"admin:fee_plan_{action}": _fee_plan for action in ("edit", "status")},
    **{f"admin:challan_{action}": _challan for action in ("detail", "cancel")},
    **{
        f"{portal}:message_{action}": _thread
        for portal in ("admin", "teacher", "student", "guardian")
        for action in ("thread", "action")
    },
    "admin:message_monitor_thread": _thread,
    **{
        f"{portal}:message_draft_delete": _draft
        for portal in ("admin", "teacher", "student", "guardian")
    },
    **{
        f"{portal}:lecture_schedule_{action}": _schedule
        for portal in ("admin", "teacher")
        for action in ("edit", "extend", "stop")
    },
}


ADMIN_PORTAL_ROLES = {Role.INSTITUTE_ADMIN, Role.SUB_ADMIN}


@pytest.mark.parametrize("route", PRODUCT_ROUTES, ids=lambda r: r.name)
def test_admin_portal_views_allow_admin_roles_only(route: Route) -> None:
    # The 403 walk only checks roles outside allowed_roles, so an extra role
    # added to an admin page would pass it unseen.
    if getattr(route.view_class, "portal", None) == "admin":
        assert set(route.view_class.allowed_roles) <= ADMIN_PORTAL_ROLES, route.name


def _url(route: Route, institute) -> str:
    build = ROUTE_OBJECTS.get(route.name)
    pk = build(institute) if build is not None else institute.pk
    if isinstance(pk, dict):  # a route with more than one pk
        return reverse(route.name, kwargs=pk)
    kwargs = {name: pk for name in route.kwarg_names}
    return reverse(route.name, kwargs=kwargs)


def _user_for(role: str, institute):
    user = make_user(
        email=f"{role}-walker@example.com",
        role=role,
        institute=None if role == Role.SUPER_ADMIN else institute,
    )
    if role == Role.TEACHER:  # a teacher account always has a profile
        with tenant_context(institute):
            create_teacher_profile(user)
    return user


@pytest.mark.django_db
@pytest.mark.parametrize("route", PRODUCT_ROUTES, ids=lambda r: r.name)
def test_anonymous_is_redirected_to_login(route: Route, institute_a) -> None:
    response = Client().get(_url(route, institute_a))
    if route.name in EMPTY_FOR_ANONYMOUS:
        assert (response.status_code, response.content) == (204, b"")
        return
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("accounts:login"))


@pytest.mark.django_db
@pytest.mark.parametrize("route", PRODUCT_ROUTES, ids=lambda r: r.name)
def test_roles_outside_allowed_roles_get_403(route: Route, institute_a) -> None:
    allowed = route.view_class.allowed_roles
    denied = [role for role in User.Role.values if role not in allowed]
    for role in denied:
        client = Client()
        client.force_login(_user_for(role, institute_a))
        status = client.get(_url(route, institute_a)).status_code
        assert status == 403, f"{route.name}: {role} got {status}"


@pytest.mark.django_db
@pytest.mark.parametrize("route", PRODUCT_ROUTES, ids=lambda r: r.name)
def test_an_allowed_role_gets_through(route: Route, institute_a) -> None:
    feature = getattr(route.view_class, "feature_key", None)
    if feature and feature not in institute_a.features:
        # A Premium feature (fees): the walker's institute is on Basic.
        institute_a.plan = Plan.objects.create(
            code="walker-all", name="Walker", feature_keys=sorted(ALL_FEATURE_KEYS)
        )
        institute_a.save()
    statuses = {}
    for role in route.view_class.allowed_roles:
        client = Client()
        client.force_login(_user_for(role, institute_a))
        statuses[role] = client.get(_url(route, institute_a)).status_code
    assert set(statuses.values()) & {200, 405}, f"{route.name}: {statuses}"
