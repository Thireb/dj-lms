"""Roadmap 5.3 (part 1): quiz set-up. Rows and scopes, the status rule
(SPEC 2 and 6.8), the set-up rules, the question bank protection (backlog
AS6) and the teacher pages."""

from __future__ import annotations

from datetime import timedelta

import pytest
from apps.assessments.models import (
    Question,
    QuestionKind,
    Quiz,
    QuizKind,
    QuizQuestion,
    QuizStatus,
)
from apps.assessments.services import (
    FIXED_MESSAGE,
    IN_QUIZ_MESSAGE,
    OPENED_MESSAGE,
    QuizDetails,
    add_questions,
    create_quiz,
    delete_question,
    publish_quiz,
    quiz_status,
    remove_question,
    unpublish_quiz,
    update_quiz,
)
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from tests.assessments.conftest import in_days
from tests.assessments.test_questions import add_question
from tests.conftest import cell, make_user, table_row
from tests.lectures.conftest import signed_in
from tests.school import link_teacher

LIST_URL = reverse("teacher:quiz_list")
ADD_URL = reverse("teacher:quiz_create")
ROLES = {
    Role.INSTITUTE_ADMIN,
    Role.SUB_ADMIN,
    Role.TEACHER,
    Role.STUDENT,
    Role.GUARDIAN,
}


def _details(school, **fields) -> QuizDetails:
    """Teacher 1, Morning/Math, opens in 2 days for 30 minutes."""
    values = {
        "title": "Fractions quiz",
        "kind": QuizKind.QUIZ,
        "teacher": school.teacher_1,
        "batch": school.morning,
        "subject": school.math,
        "opens_at": in_days(2),
        "duration_minutes": 30,
    }
    values.update(fields)
    return QuizDetails(**values)


def add_quiz(school, **fields) -> Quiz:
    institute = school.math.institute
    with tenant_context(institute):
        return create_quiz(institute, _details(school, **fields))


def _in(quiz, function, *args, **kwargs):
    with tenant_context(quiz.institute):
        return function(quiz, *args, **kwargs)


def ready_quiz(school, **fields) -> tuple[Quiz, list[Question]]:
    """A quiz with two bank questions (2 and 3 marks)."""
    quiz = add_quiz(school, **fields)
    first = add_question(school, marks=2)
    second = add_question(
        school, kind=QuestionKind.SHORT, options=(), correct=None, marks=3, text="Why?"
    )
    _in(quiz, add_questions, [first, second])
    return quiz, [first, second]


def opened(quiz: Quiz, minutes_ago: int = 1) -> Quiz:
    """Publish and move Opens into the past, which the services refuse."""
    # unscoped: test set-up outside a tenant context.
    Quiz.unscoped.filter(pk=quiz.pk).update(
        is_published=True,
        opens_at=timezone.now() - timedelta(minutes=minutes_ago),
    )
    quiz.refresh_from_db()
    return quiz


def _visible(user) -> set[int]:
    with tenant_context(user.institute):
        return set(Quiz.objects.for_user(user).values_list("pk", flat=True))


def _form(school, **fields) -> dict[str, str]:
    day = timezone.localtime(in_days(3)).date()
    values = {
        "title": "Ratio exam",
        "kind": "exam",
        "batch_subject": f"{school.morning.pk}:{school.math.pk}",
        "opens_date": day.isoformat(),
        "opens_time": "10:00",
        "duration_minutes": "45",
        "pass_marks": "",
        "require_full_screen": "on",
    }
    values.update(fields)
    return values


# Status (SPEC 2 and 6.8)


@pytest.mark.django_db
def test_status_from_draft_to_closed(school) -> None:
    quiz = add_quiz(school, duration_minutes=30)
    opens = quiz.opens_at
    assert quiz_status(quiz, opens) == QuizStatus.DRAFT
    quiz.is_published = True
    minute = timedelta(minutes=1)
    assert quiz_status(quiz, opens - minute) == QuizStatus.SCHEDULED
    assert quiz_status(quiz, opens) == QuizStatus.LIVE
    # Closes after opens + duration + 10 minutes.
    assert quiz_status(quiz, opens + 39 * minute) == QuizStatus.LIVE
    assert quiz.closes_at == opens + 40 * minute
    assert quiz_status(quiz, opens + 40 * minute) == QuizStatus.CLOSED


# Rows and scopes


@pytest.mark.django_db
def test_no_context_and_anonymous_see_nothing(school, anonymous_user) -> None:
    ready_quiz(school)
    for model in (Quiz, QuizQuestion):
        assert not model.objects.exists()
        assert not model.objects.for_user(anonymous_user).exists()


@pytest.mark.django_db
def test_scopes(school, institute_a, institute_b) -> None:
    draft = add_quiz(school, title="Draft")
    published = add_quiz(school, title="Published")
    _in(published, add_questions, [add_question(school)])
    _in(published, publish_quiz)
    link_teacher(school.teacher_2, {school.evening: [school.physics]})
    theirs = add_quiz(
        school, teacher=school.teacher_2, batch=school.evening, subject=school.physics
    )
    admin_a = make_user(
        email="admin-a@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_a
    )
    admin_b = make_user(
        email="admin-b@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_b
    )
    assert _visible(admin_a) == {draft.pk, published.pk, theirs.pk}
    assert _visible(admin_b) == set()
    assert _visible(school.teacher_1.user) == {draft.pk, published.pk}
    assert _visible(school.teacher_2.user) == {theirs.pk}
    # Students and guardians: published only, their batch and subject only.
    assert _visible(school.student_1.user) == {published.pk}
    assert _visible(school.guardian_1.user) == {published.pk}
    assert _visible(school.student_2.user) == set()
    with tenant_context(institute_a):
        for user in (school.student_1.user, school.guardian_1.user):
            assert not QuizQuestion.objects.for_user(user).exists()
        teacher_2 = QuizQuestion.objects.for_user(school.teacher_2.user)
        assert not teacher_2.exists()


# Set-up rules


@pytest.mark.django_db
def test_create_rules(school) -> None:
    with pytest.raises(ValidationError) as error:
        add_quiz(school, subject=school.physics)
    assert error.value.message_dict == {
        "subject": ["The teacher does not teach this subject."]
    }
    with pytest.raises(ValidationError) as error:
        add_quiz(school, opens_at=in_days(-0.01))
    assert error.value.message_dict == {
        "opens_at": ["Choose an opening time in the future."]
    }


@pytest.mark.django_db
def test_exam_settings_only_for_an_exam(school) -> None:
    quiz = add_quiz(school, require_full_screen=True, flag_tab_leaving=True)
    assert not quiz.require_full_screen and not quiz.flag_tab_leaving
    exam = add_quiz(
        school, kind=QuizKind.EXAM, require_full_screen=True, flag_tab_leaving=True
    )
    assert exam.require_full_screen and exam.flag_tab_leaving


@pytest.mark.django_db
def test_add_questions_of_the_subject_only(school) -> None:
    link_teacher(school.teacher_1, {school.morning: [school.math, school.physics]})
    quiz = add_quiz(school)
    math = add_question(school)
    physics = add_question(school, subject=school.physics)
    assert _in(quiz, add_questions, [math, math]) == 1
    assert _in(quiz, add_questions, [math]) == 0  # already in
    with pytest.raises(ValidationError, match="of this subject"):
        _in(quiz, add_questions, [physics])
    link_teacher(school.teacher_2, {school.morning: [school.math]})
    other = add_question(school, teacher=school.teacher_2)
    with pytest.raises(ValidationError, match="from your bank"):
        _in(quiz, add_questions, [other])


@pytest.mark.django_db
def test_positions_follow_the_order_added(school) -> None:
    quiz, questions = ready_quiz(school)
    third = add_question(school, text="Third?")
    _in(quiz, add_questions, [third])
    # unscoped: test assertion outside a tenant context.
    items = QuizQuestion.unscoped.filter(quiz=quiz).order_by("position")
    assert [item.question for item in items] == [*questions, third]
    assert [item.position for item in items] == [1, 2, 3]


@pytest.mark.django_db
def test_publish_rules(school) -> None:
    empty = add_quiz(school)
    with pytest.raises(ValidationError, match="at least one question"):
        _in(empty, publish_quiz)
    quiz, _ = ready_quiz(school, pass_marks=6)  # total is 5
    with pytest.raises(ValidationError, match=r"more than the total \(5\)"):
        _in(quiz, publish_quiz)
    quiz.pass_marks = 5
    with tenant_context(quiz.institute):
        quiz.save()
    assert _in(quiz, publish_quiz).is_published
    assert not _in(quiz, unpublish_quiz).is_published


@pytest.mark.django_db
def test_publish_refuses_a_past_opening(school) -> None:
    quiz, _ = ready_quiz(school)
    # unscoped: test set-up, a draft whose Opens time passed.
    Quiz.unscoped.filter(pk=quiz.pk).update(opens_at=in_days(-0.01))
    quiz.refresh_from_db()
    with pytest.raises(ValidationError, match="opening time has passed"):
        _in(quiz, publish_quiz)


@pytest.mark.django_db
def test_an_opened_quiz_is_fixed(school) -> None:
    quiz, questions = ready_quiz(school)
    opened(quiz)
    item = QuizQuestion.unscoped.filter(quiz=quiz).first()  # unscoped: test
    for change in (
        lambda: _in(quiz, update_quiz, _details(school, title="New")),
        lambda: _in(quiz, add_questions, [add_question(school, text="Late?")]),
        lambda: _in(quiz, remove_question, item),
        lambda: _in(quiz, unpublish_quiz),
    ):
        with pytest.raises(ValidationError) as error:
            change()
        assert error.value.messages == [OPENED_MESSAGE]


@pytest.mark.django_db
def test_update_rules(school) -> None:
    link_teacher(school.teacher_1, {school.morning: [school.math, school.physics]})
    quiz, _ = ready_quiz(school)
    saved = _in(quiz, update_quiz, _details(school, title="Renamed", pass_marks=5))
    assert saved.title == "Renamed" and saved.pass_marks == 5
    with pytest.raises(ValidationError) as error:
        _in(quiz, update_quiz, _details(school, pass_marks=6))
    assert error.value.message_dict == {
        "pass_marks": ["Pass marks are more than the total (5)."]
    }
    with pytest.raises(ValidationError, match="Remove the questions first"):
        _in(quiz, update_quiz, _details(school, subject=school.physics))
    with pytest.raises(ValidationError) as error:
        _in(quiz, update_quiz, _details(school, teacher=school.teacher_2))
    assert "teacher" in error.value.message_dict


# Question bank protection (backlog AS6)


@pytest.mark.django_db
def test_question_in_a_quiz_cannot_be_deleted(school) -> None:
    quiz, (first, _) = ready_quiz(school)
    with tenant_context(quiz.institute), pytest.raises(ValidationError) as error:
        delete_question(first)
    assert error.value.messages == [IN_QUIZ_MESSAGE]
    item = QuizQuestion.unscoped.get(quiz=quiz, question=first)  # unscoped: test
    _in(quiz, remove_question, item)
    with tenant_context(quiz.institute):
        delete_question(first)
    assert not Question.unscoped.filter(pk=first.pk).exists()  # unscoped: test


@pytest.mark.django_db
def test_question_of_an_opened_quiz_cannot_change(school) -> None:
    quiz, (first, _) = ready_quiz(school)
    assert add_question(school, first, text="Edited before").text == "Edited before"
    opened(quiz)
    with pytest.raises(ValidationError) as error:
        add_question(school, first, text="Edited after")
    assert error.value.messages == [FIXED_MESSAGE]


# Pages


@pytest.mark.django_db
def test_pages_refuse_other_roles(school) -> None:
    quiz, _ = ready_quiz(school)
    item = QuizQuestion.unscoped.filter(quiz=quiz).first()  # unscoped: test
    pages = [
        LIST_URL,
        ADD_URL,
        reverse("teacher:quiz_detail", kwargs={"pk": quiz.pk}),
        reverse("teacher:quiz_edit", kwargs={"pk": quiz.pk}),
        reverse("teacher:quiz_add_questions", kwargs={"pk": quiz.pk}),
    ]
    actions = [
        reverse("teacher:quiz_publish", kwargs={"pk": quiz.pk}),
        reverse("teacher:quiz_unpublish", kwargs={"pk": quiz.pk}),
        reverse(
            "teacher:quiz_remove_question",
            kwargs={"pk": quiz.pk, "item_pk": item.pk},
        ),
    ]
    for role in ROLES - {Role.TEACHER}:
        user = make_user(
            email=f"{role}@example.com", role=role, institute=school.math.institute
        )
        client = signed_in(user)
        for url in pages:
            assert client.get(url).status_code == 403, (role, url)
        for url in actions:
            assert client.post(url).status_code == 403, (role, url)


@pytest.mark.django_db
def test_other_teacher_and_institute_get_404(school) -> None:
    quiz, _ = ready_quiz(school)
    item = QuizQuestion.unscoped.filter(quiz=quiz).first()  # unscoped: test
    pk = quiz.pk
    for user in (school.teacher_2.user, school.teacher_b.user):
        client = signed_in(user)
        for name in ("detail", "edit", "add_questions"):
            url = reverse(f"teacher:quiz_{name}", kwargs={"pk": pk})
            assert client.get(url).status_code == 404, name
        for name in ("publish", "unpublish"):
            url = reverse(f"teacher:quiz_{name}", kwargs={"pk": pk})
            assert client.post(url).status_code == 404, name
        url = reverse(
            "teacher:quiz_remove_question", kwargs={"pk": pk, "item_pk": item.pk}
        )
        assert client.post(url).status_code == 404
    quiz.refresh_from_db()
    assert not quiz.is_published


@pytest.mark.django_db
def test_remove_needs_an_item_of_this_quiz(school) -> None:
    quiz, _ = ready_quiz(school)
    other, _ = ready_quiz(school, title="Other")
    item = QuizQuestion.unscoped.filter(quiz=other).first()  # unscoped: test
    url = reverse(
        "teacher:quiz_remove_question", kwargs={"pk": quiz.pk, "item_pk": item.pk}
    )
    assert signed_in(school.teacher_1.user).post(url).status_code == 404
    assert QuizQuestion.unscoped.filter(pk=item.pk).exists()  # unscoped: test


@pytest.mark.django_db
def test_list_empty_then_rows(school) -> None:
    client = signed_in(school.teacher_1.user)
    html = client.get(LIST_URL).content.decode()
    assert "No quizzes yet." in html
    assert f'href="{LIST_URL}"' in html  # the menu link is built
    quiz, _ = ready_quiz(school)
    add_quiz(school, title="Empty draft", kind=QuizKind.EXAM)
    html = client.get(LIST_URL).content.decode()
    row = table_row(html, "Fractions quiz")
    assert cell(row, "questions") == ["2", "questions,", "5", "marks"]
    assert cell(row, "status") == ["Draft"]
    assert cell(row, "duration") == ["30", "min"]
    assert cell(table_row(html, "Empty draft"), "questions") == [
        "0",
        "questions,",
        "0",
        "marks",
    ]
    html = client.get(LIST_URL, {"kind": "exam"}).content.decode()
    assert "Empty draft" in html and "Fractions quiz" not in html
    _in(quiz, publish_quiz)
    html = client.get(LIST_URL, {"status": "scheduled"}).content.decode()
    assert "Fractions quiz" in html and "Empty draft" not in html


@pytest.mark.django_db
def test_add_quiz_page(school) -> None:
    client = signed_in(school.teacher_1.user)
    response = client.post(ADD_URL, _form(school, flag_tab_leaving="on"))
    quiz = Quiz.unscoped.get()  # unscoped: test assertion
    assert response.status_code == 302
    assert response["Location"] == reverse(
        "teacher:quiz_detail", kwargs={"pk": quiz.pk}
    )
    assert quiz.kind == QuizKind.EXAM and quiz.duration_minutes == 45
    assert quiz.require_full_screen and quiz.flag_tab_leaving
    assert not quiz.is_published
    karachi = timezone.get_fixed_timezone(300)  # the teacher's zone
    assert timezone.localtime(quiz.opens_at, karachi).strftime("%H:%M") == "10:00"


@pytest.mark.django_db
def test_detail_add_publish_and_remove(school) -> None:
    quiz = add_quiz(school)
    question = add_question(school)
    client = signed_in(school.teacher_1.user)
    detail = reverse("teacher:quiz_detail", kwargs={"pk": quiz.pk})
    add = reverse("teacher:quiz_add_questions", kwargs={"pk": quiz.pk})

    html = client.get(detail).content.decode()
    assert "Draft: students do not see it" in html
    assert f"{reverse('teacher:question_create')}?quiz={quiz.pk}" in html
    html = client.get(add).content.decode()
    assert "What is half of 10? (2 marks)" in html
    response = client.post(add, {"questions": [str(question.pk)]})
    assert response.status_code == 302 and response["Location"] == detail

    publish = reverse("teacher:quiz_publish", kwargs={"pk": quiz.pk})
    assert client.get(publish).status_code == 405
    assert client.post(publish).status_code == 302
    quiz.refresh_from_db()
    assert quiz.is_published
    html = client.get(detail).content.decode()
    assert "Students see it now." in html
    assert "Back to draft" in html

    item = QuizQuestion.unscoped.get(quiz=quiz)  # unscoped: test
    remove = reverse(
        "teacher:quiz_remove_question", kwargs={"pk": quiz.pk, "item_pk": item.pk}
    )
    client.post(remove)
    assert not QuizQuestion.unscoped.filter(quiz=quiz).exists()  # unscoped: test
    assert Question.unscoped.filter(pk=question.pk).exists()  # unscoped: test


@pytest.mark.django_db
def test_opened_quiz_pages_are_read_only(school) -> None:
    quiz, _ = ready_quiz(school)
    opened(quiz)
    client = signed_in(school.teacher_1.user)
    detail = reverse("teacher:quiz_detail", kwargs={"pk": quiz.pk})
    html = client.get(detail).content.decode()
    assert "Live. It closes" in html
    assert "Add from bank" not in html and ">Remove<" not in html
    for name in ("edit", "add_questions"):
        response = client.get(reverse(f"teacher:quiz_{name}", kwargs={"pk": quiz.pk}))
        assert response.status_code == 302 and response["Location"] == detail


@pytest.mark.django_db
def test_new_question_from_a_quiz_joins_it(school) -> None:
    quiz = add_quiz(school)
    client = signed_in(school.teacher_1.user)
    url = f"{reverse('teacher:question_create')}?quiz={quiz.pk}"
    html = client.get(url).content.decode()
    assert f"added to {quiz.title}" in html
    response = client.post(
        url,
        {
            "kind": "short",
            "subject": str(school.math.pk),
            "text": "Explain a ratio.",
            "marks": "4",
        },
    )
    assert response["Location"] == reverse(
        "teacher:quiz_detail", kwargs={"pk": quiz.pk}
    )
    item = QuizQuestion.unscoped.get(quiz=quiz)  # unscoped: test assertion
    assert item.question.text == "Explain a ratio."


@pytest.mark.django_db
def test_question_page_shows_the_bank_protection(school) -> None:
    quiz, (first, _) = ready_quiz(school)
    client = signed_in(school.teacher_1.user)
    delete = reverse("teacher:question_delete", kwargs={"pk": first.pk})
    response = client.post(delete, follow=True)
    assert IN_QUIZ_MESSAGE in response.content.decode()
    assert Question.unscoped.filter(pk=first.pk).exists()  # unscoped: test
    opened(quiz)
    edit = reverse("teacher:question_edit", kwargs={"pk": first.pk})
    response = client.post(
        edit,
        {
            "kind": "mcq",
            "subject": str(school.math.pk),
            "text": "Changed",
            "marks": "2",
            "option_1": "4",
            "option_2": "5",
            "correct": "2",
        },
    )
    assert response.status_code == 200
    assert FIXED_MESSAGE in response.content.decode()
