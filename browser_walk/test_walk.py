"""Browser walk: open every portal page as its demo role at 360px and 1440px
in Chromium, on the `seed_demo` data.

Run it with `./scripts/browser-walk.sh` (not part of `uv run pytest`). A page
fails when it does not answer 200, scrolls sideways or logs a console error.
axe (WCAG A and AA) findings are listed; `WALK_AXE_FAIL=1` makes them fail
too. `WALK_SHOTS=<dir>` saves a screenshot of each page. `WALK_ONLY=<text>`
walks only the routes whose name has that text (for example `teacher:quiz`).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from apps.academics.models import Batch, ClassLabel, Subject
from apps.accounts.models import User
from apps.assessments.models import (
    Assignment,
    Question,
    Quiz,
    QuizAttempt,
    Submission,
)
from apps.institutes.models import Institute
from apps.lectures.models import Lecture, LectureStatus, RecurringSchedule
from apps.messaging.models import ThreadMember
from apps.people.models import StudentProfile, TeacherProfile
from django.core.management import call_command
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver, reverse

AXE = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js"
AXE_RUN = (
    "axe.run({runOnly: ['wcag2a', 'wcag2aa']})"
    ".then(r => r.violations.map(v => v.id + ' x' + v.nodes.length))"
)
WIDTHS = (360, 1440)
USERS = {
    "super": "demo-super@example.com",
    "admin": "demo-admin@example.com",
    "teacher": "demo-teacher@example.com",
    "student": "demo-student@example.com",
    "guardian": "demo-guardian@example.com",
}
# Not pages: a file download and the HTMX parts that pages reload.
SKIPPED = {
    "admin:student_bulk_template",
    "admin:message_unread",
    "teacher:message_unread",
    "student:message_unread",
    "guardian:message_unread",
    "teacher:up_next",
    "student:up_next",
    "notifications:count",
    "notifications:panel",
}
# Pages outside the portal URLs that every role opens in its own shell.
SHARED = {
    "notifications:list": ["admin", "teacher", "student", "guardian"],
    "accounts:profile": list(USERS),
    "accounts:change_password": list(USERS),
}

DEMO_TEACHER = "demo-teacher@example.com"
DEMO_STUDENT = "demo-student@example.com"


# Demo rows for the routes with a pk. Uses `unscoped` on purpose: a dev tool
# that reads the seed data outside a request.
def _pk(row: Any) -> dict[str, int] | None:
    return {"pk": row.pk} if row is not None else None


def _lecture(status: str) -> Callable[[], dict[str, int] | None]:
    def build() -> dict[str, int] | None:
        rows = Lecture.unscoped.filter(teacher__user__email=DEMO_TEACHER)
        return _pk(rows.filter(status=status).order_by("-starts_at").first())

    return build


def _quiz_attempt() -> dict[str, int] | None:
    attempt = QuizAttempt.unscoped.order_by("pk").first()
    if attempt is None:
        return None
    return {"pk": attempt.quiz_id, "attempt_pk": attempt.pk}


def _grade() -> dict[str, int] | None:
    row = Submission.unscoped.order_by("pk").first()
    if row is None:
        return None
    return {"pk": row.assignment_id, "submission_pk": row.pk}


def _closed_quiz() -> dict[str, int] | None:
    attempt = QuizAttempt.unscoped.order_by("pk").first()
    return {"pk": attempt.quiz_id} if attempt else None


def _student_assignment() -> dict[str, int] | None:
    rows = Assignment.unscoped.filter(submissions__student__user__email=DEMO_STUDENT)
    return _pk(rows.first())


def _own(model: Any) -> Callable[[], dict[str, int] | None]:
    def build() -> dict[str, int] | None:
        rows = model.unscoped.filter(teacher__user__email=DEMO_TEACHER)
        return _pk(rows.order_by("pk").first())

    return build


def _first(model: Any) -> Callable[[], dict[str, int] | None]:
    return lambda: _pk(model.unscoped.order_by("pk").first())


def _student() -> dict[str, int] | None:
    return _pk(StudentProfile.unscoped.filter(user__email=DEMO_STUDENT).first())


def _teacher() -> dict[str, int] | None:
    return _pk(TeacherProfile.unscoped.filter(user__email=DEMO_TEACHER).first())


def _demo_thread(email: str) -> Callable[[], dict[str, int] | None]:
    def build() -> dict[str, int] | None:
        row = ThreadMember.unscoped.filter(user__email=email).order_by("pk").first()
        return {"pk": row.thread_id} if row else None

    return build


OBJECTS: dict[str, Callable[[], dict[str, int] | None]] = {
    "super:institute_edit": lambda: _pk(Institute.objects.order_by("pk").first()),
    "admin:class_edit": _first(ClassLabel),
    "admin:batch_edit": _first(Batch),
    "admin:subject_edit": _first(Subject),
    "admin:student_edit": _student,
    "admin:teacher_edit": _teacher,
    "admin:lecture_detail": _lecture(LectureStatus.LIVE),
    "admin:lecture_edit": _lecture(LectureStatus.SCHEDULED),
    "admin:lecture_schedule_edit": _own(RecurringSchedule),
    "admin:lecture_schedule_extend": _own(RecurringSchedule),
    "admin:quiz_detail": _closed_quiz,
    "teacher:lecture_detail": _lecture(LectureStatus.LIVE),
    "teacher:lecture_edit": _lecture(LectureStatus.SCHEDULED),
    "teacher:lecture_attendance": _lecture(LectureStatus.FINISHED),
    "teacher:lecture_schedule_edit": _own(RecurringSchedule),
    "teacher:lecture_schedule_extend": _own(RecurringSchedule),
    "teacher:assignment_detail": lambda: _pk(
        Assignment.unscoped.filter(submissions__isnull=False).first()
    ),
    "teacher:assignment_edit": _own(Assignment),
    "teacher:assignment_grade": _grade,
    "teacher:question_edit": _own(Question),
    "teacher:quiz_detail": _closed_quiz,
    "teacher:quiz_edit": lambda: _pk(Quiz.unscoped.filter(is_published=False).first()),
    "teacher:quiz_add_questions": lambda: _pk(
        Quiz.unscoped.filter(is_published=False).first()
    ),
    "teacher:quiz_attempt": _quiz_attempt,
    "student:assignment_detail": _student_assignment,
    "student:quiz_detail": _closed_quiz,
    "admin:message_thread": _demo_thread("demo-admin@example.com"),
    "admin:message_monitor_thread": _demo_thread(DEMO_STUDENT),
    "teacher:message_thread": _demo_thread(DEMO_TEACHER),
    "student:message_thread": _demo_thread(DEMO_STUDENT),
    "guardian:message_thread": _demo_thread("demo-guardian@example.com"),
}


def _routes() -> list[tuple[str, Any, tuple[str, ...]]]:
    """(name, view class, URL kwargs) of every GET page in the portals."""
    found = []

    def walk(patterns: list[Any], namespace: str) -> None:
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                walk(pattern.url_patterns, pattern.namespace or namespace)
            elif isinstance(pattern, URLPattern) and pattern.name:
                view = getattr(pattern.callback, "view_class", None)
                name = f"{namespace}:{pattern.name}"
                if view is None or (namespace not in USERS and name not in SHARED):
                    continue
                if "get" not in view.http_method_names:
                    continue
                if name not in SKIPPED:
                    found.append((name, view, tuple(pattern.pattern.converters)))

    walk(get_resolver("config.urls").url_patterns, "")
    return found


def _pages() -> tuple[dict[str, list[tuple[str, str]]], list[str]]:
    only = os.environ.get("WALK_ONLY", "")
    pages: dict[str, list[tuple[str, str]]] = {role: [] for role in USERS}
    not_walked = []
    for name, _view, kwargs in _routes():
        if only not in name:
            continue
        values = OBJECTS[name]() if kwargs and name in OBJECTS else {}
        if kwargs and not values:
            not_walked.append(name)
            continue
        for role in SHARED.get(name, [name.split(":")[0]]):
            pages[role].append((name, reverse(name, kwargs=values)))
    return pages, not_walked


def _cookie(email: str) -> str:
    client = Client()
    client.force_login(User.objects.get(email=email))
    return client.cookies["sessionid"].value


@pytest.mark.django_db(transaction=True)
def test_browser_walk(live_server: Any, settings: Any) -> None:
    from playwright.sync_api import sync_playwright

    settings.DEBUG = True  # seed_demo refuses to run without it
    call_command("seed_demo")
    settings.DEBUG = False
    pages, not_walked = _pages()
    shots = os.environ.get("WALK_SHOTS")
    if shots:
        Path(shots).mkdir(parents=True, exist_ok=True)
    problems, axe_found, opened = [], [], 0
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for role, rows in pages.items():
            if not rows:
                continue
            cookie = _cookie(USERS[role])
            for width in WIDTHS:
                context = browser.new_context(viewport={"width": width, "height": 900})
                context.add_cookies(
                    [{"name": "sessionid", "value": cookie, "url": live_server.url}]
                )
                page = context.new_page()
                errors: list[str] = []
                page.on(
                    "console",
                    lambda m, e=errors: m.type == "error" and e.append(m.text),
                )
                for name, path in rows:
                    errors.clear()
                    response = page.goto(live_server.url + path)
                    opened += 1
                    status = response.status if response else 0
                    wide = page.evaluate(
                        "document.documentElement.scrollWidth > window.innerWidth"
                    )
                    page.add_script_tag(url=AXE)
                    violations = page.evaluate(AXE_RUN)
                    where = f"{name} at {width}px ({path})"
                    if status != 200:
                        problems.append(f"{where}: status {status}")
                    if wide:
                        problems.append(f"{where}: scrolls sideways")
                    if errors:
                        problems.append(f"{where}: console {errors}")
                    if violations:
                        axe_found.append(f"{where}: axe {violations}")
                    if shots:
                        file = f"{name.replace(':', '_')}_{width}.png"
                        page.screenshot(path=str(Path(shots) / file), full_page=True)
                context.close()
        browser.close()
    print(f"\nOpened {opened} pages for {len(USERS)} roles at {WIDTHS} px.")
    for line in [*problems, *axe_found]:
        print(line)
    if not_walked:
        print("Not walked (add the route to OBJECTS):", ", ".join(sorted(not_walked)))
    assert not problems
    if os.environ.get("WALK_AXE_FAIL") == "1":
        assert not axe_found
