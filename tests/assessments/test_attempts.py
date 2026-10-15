"""Roadmap 5.3 (part 2a): the student's attempt. Start while live, one
attempt, the deadline, MCQ auto-marking (SPEC 6.8), scopes and pages."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.assessments.models import (
    AttemptAnswer,
    AttemptStatus,
    QuestionKind,
    QuestionOption,
    Quiz,
    QuizAttempt,
)
from apps.assessments.services import (
    DONE_MESSAGE,
    NOT_LIVE_MESSAGE,
    add_questions,
    attempt_items,
    close_expired,
    publish_quiz,
    save_attempt,
    start_attempt,
    student_quizzes,
)
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.people.models import ProfileStatus, StudentProfile
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from tests.assessments.test_questions import add_question
from tests.assessments.test_quizzes import _in, add_quiz, opened
from tests.conftest import cell, make_user, table_row
from tests.lectures.conftest import signed_in
from tests.people.conftest import student
from tests.school import link_student

LIST_URL = reverse("student:quiz_list")


def live_quiz(school, *, short: bool = True, **fields):
    """A live quiz (opened a minute ago) with two MCQ questions (2 and 1
    marks) and, with ``short``, a short answer question (3 marks)."""
    quiz = add_quiz(school, **fields)
    questions = [
        add_question(school, text="Half of 10?", marks=2),  # options 4, 5, 6
        add_question(
            school, text="Is 1 odd?", options=("Yes", "No"), correct=0, marks=1
        ),
    ]
    if short:
        questions.append(
            add_question(
                school,
                kind=QuestionKind.SHORT,
                options=(),
                correct=None,
                marks=3,
                text="Explain zero.",
            )
        )
    _in(quiz, add_questions, questions)
    return opened(quiz), questions


def _start(quiz, student, now=None):
    with tenant_context(quiz.institute):
        return start_attempt(quiz, student, now=now)


def _save(attempt, answers, **kwargs):
    with tenant_context(attempt.institute):
        return save_attempt(attempt, answers, **kwargs)


def _option(question, text):
    # unscoped: test set-up outside a tenant context.
    return QuestionOption.unscoped.get(question=question, text=text).pk


def _items(attempt):
    with tenant_context(attempt.institute):
        return {item.question.text: item.pk for item in attempt_items(attempt)}


# Start


@pytest.mark.django_db
def test_start_only_while_live(school) -> None:
    draft = add_quiz(school)
    with pytest.raises(ValidationError) as error:
        _start(draft, school.student_1)
    assert error.value.messages == [NOT_LIVE_MESSAGE]
    quiz, _ = live_quiz(school, title="Live")
    assert _start(quiz, school.student_1).status == AttemptStatus.IN_PROGRESS
    # Closed 30 + 10 minutes after Opens.
    with pytest.raises(ValidationError) as error:
        _start(quiz, _make_student(school), now=quiz.opens_at + timedelta(minutes=40))
    assert error.value.messages == [NOT_LIVE_MESSAGE]


def _make_student(school):
    profile = student(school.morning.institute, "s9-a@example.com")
    link_student(profile, {school.morning: [school.math]})
    return profile


@pytest.mark.django_db
def test_one_attempt_per_student(school) -> None:
    quiz, _ = live_quiz(school)
    first = _start(quiz, school.student_1)
    _save(first, {}, submit=True)
    again = _start(quiz, school.student_1)
    assert again.pk == first.pk
    assert QuizAttempt.unscoped.count() == 1  # unscoped: test assertion


@pytest.mark.django_db
def test_only_students_of_the_batch_and_subject(school) -> None:
    quiz, _ = live_quiz(school)
    with pytest.raises(ValidationError, match="not for this student"):
        _start(quiz, school.student_2)
    # unscoped: test set-up outside a tenant context.
    StudentProfile.unscoped.filter(pk=school.student_1.pk).update(
        status=ProfileStatus.INACTIVE
    )
    with pytest.raises(ValidationError, match="not for this student"):
        _start(quiz, school.student_1)


@pytest.mark.django_db
def test_deadline_is_the_duration_or_the_close(school) -> None:
    quiz, _ = live_quiz(school, duration_minutes=30)
    early = _start(quiz, school.student_1, now=quiz.opens_at)
    assert early.deadline == quiz.opens_at + timedelta(minutes=30)
    late_start = quiz.opens_at + timedelta(minutes=35)
    late = _start(quiz, _make_student(school), now=late_start)
    assert late.deadline == quiz.closes_at  # 5 minutes left, not 30


@pytest.mark.django_db
def test_shuffle_keeps_every_question_once(school) -> None:
    quiz, questions = live_quiz(school, shuffle_questions=True)
    attempt = _start(quiz, school.student_1)
    assert sorted(_items(attempt)) == sorted(q.text for q in questions)
    plain, _ = live_quiz(school, title="Plain")
    attempt = _start(plain, school.student_1)
    assert list(_items(attempt)) == ["Half of 10?", "Is 1 odd?", "Explain zero."]


# Marking (SPEC 6.8)


@pytest.mark.django_db
def test_mcq_only_quiz_is_graded_at_submit(school) -> None:
    quiz, (half, odd) = live_quiz(school, short=False)
    attempt = _start(quiz, school.student_1)
    items = _items(attempt)
    saved = _save(
        attempt,
        {
            items["Half of 10?"]: _option(half, "5"),
            items["Is 1 odd?"]: _option(odd, "No"),
        },
        submit=True,
    )
    assert saved.status == AttemptStatus.GRADED
    assert saved.score == Decimal("2")  # 2 right + 0 wrong
    # unscoped: test assertion outside a tenant context.
    marks = dict(AttemptAnswer.unscoped.values_list("item__question__text", "marks"))
    assert marks == {"Half of 10?": Decimal("2"), "Is 1 odd?": Decimal("0")}


@pytest.mark.django_db
def test_short_answer_waits_for_the_teacher(school) -> None:
    quiz, (half, odd, _) = live_quiz(school)
    attempt = _start(quiz, school.student_1)
    items = _items(attempt)
    saved = _save(
        attempt,
        {
            items["Half of 10?"]: _option(half, "5"),
            items["Is 1 odd?"]: _option(odd, "Yes"),
            items["Explain zero."]: "  Nothing.  ",
        },
        submit=True,
    )
    assert saved.status == AttemptStatus.SUBMITTED
    assert saved.score is None
    rows = AttemptAnswer.unscoped.all()  # unscoped: test assertion
    assert {row.item.question.text: row.marks for row in rows} == {
        "Half of 10?": Decimal("2"),
        "Is 1 odd?": Decimal("1"),
        "Explain zero.": None,
    }
    assert rows.get(item__question__text="Explain zero.").text == "Nothing."


@pytest.mark.django_db
def test_unanswered_mcq_gets_zero(school) -> None:
    quiz, _ = live_quiz(school, short=False)
    saved = _save(_start(quiz, school.student_1), {}, submit=True)
    assert saved.status == AttemptStatus.GRADED and saved.score == Decimal("0")


@pytest.mark.django_db
def test_save_keeps_the_attempt_open(school) -> None:
    quiz, (half, *_rest) = live_quiz(school)
    attempt = _start(quiz, school.student_1)
    item = _items(attempt)["Half of 10?"]
    saved = _save(attempt, {item: _option(half, "4")})
    assert saved.status == AttemptStatus.IN_PROGRESS
    _save(attempt, {item: _option(half, "5")})
    row = AttemptAnswer.unscoped.get()  # unscoped: test assertion
    assert row.option.text == "5" and row.marks is None


@pytest.mark.django_db
def test_option_must_belong_to_the_question(school) -> None:
    quiz, (half, odd, _) = live_quiz(school)
    attempt = _start(quiz, school.student_1)
    item = _items(attempt)["Half of 10?"]
    with pytest.raises(ValidationError, match="question's options"):
        _save(attempt, {item: _option(odd, "Yes")})


@pytest.mark.django_db
def test_submitted_attempt_cannot_change(school) -> None:
    quiz, _ = live_quiz(school)
    attempt = _start(quiz, school.student_1)
    _save(attempt, {}, submit=True)
    with pytest.raises(ValidationError) as error:
        _save(attempt, {}, submit=True)
    assert error.value.messages == [DONE_MESSAGE]


# Time (SPEC 6.8: auto-submit when the timer ends)


@pytest.mark.django_db
def test_answers_in_the_grace_minute_count(school) -> None:
    quiz, (half, *_rest) = live_quiz(school, short=False)
    attempt = _start(quiz, school.student_1)
    item = _items(attempt)["Half of 10?"]
    at = attempt.deadline + timedelta(seconds=50)
    saved = _save(attempt, {item: _option(half, "5")}, submit=True, auto=True, now=at)
    assert saved.score == Decimal("2")
    assert saved.auto_submitted and saved.submitted_at == attempt.deadline


@pytest.mark.django_db
def test_late_answers_are_not_saved(school) -> None:
    quiz, (half, *_rest) = live_quiz(school, short=False)
    attempt = _start(quiz, school.student_1)
    item = _items(attempt)["Half of 10?"]
    at = attempt.deadline + timedelta(minutes=2)
    saved = _save(attempt, {item: _option(half, "5")}, now=at)  # a Save, too late
    assert saved.status == AttemptStatus.GRADED
    assert saved.score == Decimal("0") and saved.auto_submitted


@pytest.mark.django_db
def test_an_attempt_left_open_is_submitted(school) -> None:
    quiz, (half, *_rest) = live_quiz(school, short=False)
    attempt = _start(quiz, school.student_1)
    item = _items(attempt)["Half of 10?"]
    _save(attempt, {item: _option(half, "5")})
    with tenant_context(attempt.institute):
        assert close_expired(attempt).status == AttemptStatus.IN_PROGRESS
        later = attempt.deadline + timedelta(minutes=2)
        closed = close_expired(attempt, now=later)
    assert closed.status == AttemptStatus.GRADED
    assert closed.score == Decimal("2")  # the saved answer counts
    assert closed.auto_submitted


# Scopes


@pytest.mark.django_db
def test_attempt_scopes(school, institute_a, institute_b) -> None:
    quiz, _ = live_quiz(school)
    mine = _start(quiz, school.student_1)
    _save(mine, {}, submit=True)
    admin_b = make_user(
        email="admin-b@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_b
    )

    def visible(model, user):
        with tenant_context(user.institute):
            return set(model.objects.for_user(user).values_list("pk", flat=True))

    assert visible(QuizAttempt, school.student_1.user) == {mine.pk}
    assert visible(QuizAttempt, school.guardian_1.user) == {mine.pk}
    assert visible(QuizAttempt, school.teacher_1.user) == {mine.pk}
    for user in (school.student_2.user, school.guardian_2.user, school.teacher_2.user):
        assert visible(QuizAttempt, user) == set()
    assert visible(QuizAttempt, admin_b) == set()
    answers = visible(AttemptAnswer, school.student_1.user)
    assert len(answers) == 2  # the two MCQ rows made at submit
    assert visible(AttemptAnswer, school.teacher_1.user) == answers
    # Guardians see scores, not answers (SPEC 6.8).
    assert visible(AttemptAnswer, school.guardian_1.user) == set()
    assert visible(AttemptAnswer, school.student_2.user) == set()


# Lists and pages


@pytest.mark.django_db
def test_student_list(school) -> None:
    graded, _ = live_quiz(school, short=False, title="Graded one")
    _save(_start(graded, school.student_1), {}, submit=True)
    live_quiz(school, title="Live one")
    scheduled = add_quiz(school, title="Next one")
    _in(scheduled, add_questions, [add_question(school, text="Later?")])
    _in(scheduled, publish_quiz)
    add_quiz(school, title="Draft one")
    missed, _ = live_quiz(school, title="Missed one")
    # unscoped: test set-up, a quiz that closed without an attempt.
    Quiz.unscoped.filter(pk=missed.pk).update(
        opens_at=timezone.now() - timedelta(days=1)
    )

    html = signed_in(school.student_1.user).get(LIST_URL).content.decode()
    assert "Draft one" not in html
    assert cell(table_row(html, "Graded one"), "status") == ["Graded"]
    assert cell(table_row(html, "Graded one"), "score") == ["0", "/", "3"]
    assert cell(table_row(html, "Live one"), "status") == ["Live"]
    assert cell(table_row(html, "Next one"), "status") == ["Scheduled"]
    assert cell(table_row(html, "Missed one"), "status") == ["Not", "taken"]
    with tenant_context(school.morning.institute):
        titles = [row.quiz.title for row in student_quizzes(school.student_1)]
    assert titles[-1] == "Missed one"  # closed ones last, newest first


@pytest.mark.django_db
def test_pages_refuse_other_roles(school) -> None:
    quiz, _ = live_quiz(school)
    urls = {
        name: reverse(f"student:quiz_{name}", kwargs={"pk": quiz.pk})
        for name in ("detail", "start", "attempt")
    }
    for role in {Role.INSTITUTE_ADMIN, Role.SUB_ADMIN, Role.TEACHER, Role.GUARDIAN}:
        user = make_user(
            email=f"{role}@example.com", role=role, institute=school.math.institute
        )
        client = signed_in(user)
        assert client.get(LIST_URL).status_code == 403
        assert client.get(urls["detail"]).status_code == 403
        assert client.get(urls["attempt"]).status_code == 403
        assert client.post(urls["start"]).status_code == 403


@pytest.mark.django_db
def test_other_students_get_404(school) -> None:
    quiz, _ = live_quiz(school)
    draft = add_quiz(school, title="Draft")
    for user, target in (
        (school.student_2.user, quiz),
        (school.student_b.user, quiz),
        (school.student_1.user, draft),
    ):
        client = signed_in(user)
        for name in ("detail", "attempt"):
            url = reverse(f"student:quiz_{name}", kwargs={"pk": target.pk})
            assert client.get(url).status_code == 404, (user, name)
        url = reverse("student:quiz_start", kwargs={"pk": target.pk})
        assert client.post(url).status_code == 404
    assert not QuizAttempt.unscoped.exists()  # unscoped: test assertion


@pytest.mark.django_db
def test_start_save_and_submit_pages(school) -> None:
    quiz, (half, odd, _) = live_quiz(school)
    client = signed_in(school.student_1.user)
    detail = reverse("student:quiz_detail", kwargs={"pk": quiz.pk})
    start = reverse("student:quiz_start", kwargs={"pk": quiz.pk})
    paper = reverse("student:quiz_attempt", kwargs={"pk": quiz.pk})

    html = client.get(detail).content.decode()
    assert start in html
    assert client.get(start).status_code == 405
    response = client.post(start)
    assert response["Location"] == paper

    html = client.get(paper).content.decode()
    assert 'id="attempt-form"' in html
    assert 'data-form="attempt-form"' in html
    assert "1. Half of 10? (2 marks)" in html
    assert 'name="save"' in html and 'name="submit"' in html
    attempt = QuizAttempt.unscoped.get()  # unscoped: test assertion
    items = _items(attempt)
    first = f"item_{items['Half of 10?']}"
    response = client.post(paper, {first: _option(half, "5"), "save": "1"})
    assert response["Location"] == paper
    html = client.get(paper).content.decode()
    assert f'value="{_option(half, "5")}"' in html and "checked" in html

    response = client.post(
        paper,
        {
            first: _option(half, "5"),
            f"item_{items['Is 1 odd?']}": _option(odd, "Yes"),
            f"item_{items['Explain zero.']}": "None at all.",
            "submit": "1",
        },
    )
    assert response["Location"] == detail
    attempt.refresh_from_db()
    assert attempt.status == AttemptStatus.SUBMITTED and not attempt.auto_submitted
    html = client.get(detail).content.decode()
    assert "Your teacher marks the written answers." in html
    response = client.get(paper)
    assert response["Location"] == detail  # no paper after submit


@pytest.mark.django_db
def test_timer_submit_is_marked_automatic(school) -> None:
    quiz, _ = live_quiz(school, short=False)
    client = signed_in(school.student_1.user)
    client.post(reverse("student:quiz_start", kwargs={"pk": quiz.pk}))
    paper = reverse("student:quiz_attempt", kwargs={"pk": quiz.pk})
    client.post(paper, {"auto_submit": "1"})
    attempt = QuizAttempt.unscoped.get()  # unscoped: test assertion
    assert attempt.status == AttemptStatus.GRADED and attempt.auto_submitted
    html = client.get(reverse("student:quiz_detail", kwargs={"pk": quiz.pk}))
    assert "Sent when the time ended." in html.content.decode()


@pytest.mark.django_db
def test_menu_link_is_built(school) -> None:
    html = signed_in(school.student_1.user).get(LIST_URL).content.decode()
    assert f'href="{LIST_URL}"' in html
    assert "No quizzes yet." in html
