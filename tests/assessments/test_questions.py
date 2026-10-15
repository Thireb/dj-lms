"""Roadmap 5.2 question bank: rows and scopes, the save rules (SPEC 4.16)
and the teacher pages."""

from __future__ import annotations

import pytest
from apps.assessments.models import Question, QuestionKind, QuestionOption
from apps.assessments.services import QuestionDetails, save_question
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from django.core.exceptions import ValidationError
from django.urls import reverse

from tests.conftest import cell, make_user, table_row
from tests.lectures.conftest import select_values, signed_in
from tests.school import link_teacher

LIST_URL = reverse("teacher:question_list")
ADD_URL = reverse("teacher:question_create")
ROLES = {
    Role.INSTITUTE_ADMIN,
    Role.SUB_ADMIN,
    Role.TEACHER,
    Role.STUDENT,
    Role.GUARDIAN,
}


def _details(school, **fields) -> QuestionDetails:
    """Teacher 1, Math, an MCQ with 3 options, the second correct."""
    values = {
        "teacher": school.teacher_1,
        "subject": school.math,
        "kind": QuestionKind.MCQ,
        "text": "What is half of 10?",
        "marks": 2,
        "options": ("4", "5", "6"),
        "correct": 1,
    }
    values.update(fields)
    return QuestionDetails(**values)


def add_question(school, question=None, **fields) -> Question:
    institute = school.math.institute
    with tenant_context(institute):
        return save_question(institute, _details(school, **fields), question)


def _options(question) -> list[tuple[int, str, bool]]:
    # unscoped: test assertion outside a tenant context.
    rows = QuestionOption.unscoped.filter(question=question)
    return list(rows.values_list("position", "text", "is_correct"))


def _errors(error) -> dict:
    return error.value.message_dict


def _visible(user) -> set[int]:
    with tenant_context(user.institute):
        return set(Question.objects.for_user(user).values_list("pk", flat=True))


def _form(school, **fields) -> dict[str, str]:
    values = {
        "kind": "mcq",
        "subject": str(school.math.pk),
        "text": "Which number is prime?",
        "marks": "3",
        "option_1": "4",
        "option_2": "",
        "option_3": "7",
        "option_4": "9",
        "correct": "3",
        "explanation": "7 has no factors but 1 and 7.",
    }
    values.update(fields)
    return values


# Rows and scopes


@pytest.mark.django_db
def test_mcq_saves_its_options_in_order(school) -> None:
    question = add_question(school)
    assert question.kind == QuestionKind.MCQ and question.marks == 2
    assert _options(question) == [(1, "4", False), (2, "5", True), (3, "6", False)]


@pytest.mark.django_db
def test_no_context_and_anonymous_see_nothing(school, anonymous_user) -> None:
    add_question(school)
    for model in (Question, QuestionOption):
        assert not model.objects.exists()
        assert not model.objects.for_user(anonymous_user).exists()
        assert not model.objects.for_user(None).exists()


@pytest.mark.django_db
def test_bank_is_the_teachers_own(school, institute_a, institute_b) -> None:
    link_teacher(school.teacher_2, {school.evening: [school.physics, school.math]})
    mine = add_question(school)
    theirs = add_question(school, teacher=school.teacher_2)
    admin_a = make_user(
        email="admin-a@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_a
    )
    admin_b = make_user(
        email="admin-b@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_b
    )
    assert _visible(school.teacher_1.user) == {mine.pk}
    assert _visible(school.teacher_2.user) == {theirs.pk}
    assert _visible(admin_a) == {mine.pk, theirs.pk}
    assert _visible(admin_b) == set()
    # Students and guardians never read the bank (it holds the answers).
    for user in (school.student_1.user, school.guardian_1.user):
        assert _visible(user) == set()
        with tenant_context(user.institute):
            assert not QuestionOption.objects.for_user(user).exists()
    with tenant_context(institute_a):
        teacher_2_options = QuestionOption.objects.for_user(school.teacher_2.user)
        assert set(teacher_2_options.values_list("question_id", flat=True)) == {
            theirs.pk
        }


# Save rules (SPEC 4.16)


@pytest.mark.django_db
def test_short_answer_has_no_options(school) -> None:
    question = add_question(
        school, kind=QuestionKind.SHORT, options=(), correct=None, marks=5
    )
    assert _options(question) == []
    with pytest.raises(ValidationError) as error:
        add_question(school, kind=QuestionKind.SHORT, options=("a", "b"))
    assert _errors(error) == {"options": ["A short answer question has no options."]}


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("options", "message"),
    [
        (("Only one",), "Give 2 to 6 options for an MCQ question."),
        (tuple("abcdefg"), "Give 2 to 6 options for an MCQ question."),
        (("Yes", " "), "An option is empty."),
        (("Paris", "paris "), "Two options are the same."),
    ],
)
def test_mcq_needs_two_to_six_different_options(school, options, message) -> None:
    with pytest.raises(ValidationError) as error:
        add_question(school, options=options, correct=0)
    assert _errors(error) == {"options": [message]}


@pytest.mark.django_db
def test_two_and_six_options_are_allowed(school) -> None:
    assert len(_options(add_question(school, options=("Yes", "No"), correct=0))) == 2
    six = add_question(school, options=tuple("abcdef"), correct=5)
    assert [row[2] for row in _options(six)] == [False] * 5 + [True]


@pytest.mark.django_db
@pytest.mark.parametrize("correct", [None, 3, -1])
def test_mcq_needs_one_correct_option(school, correct) -> None:
    with pytest.raises(ValidationError) as error:
        add_question(school, correct=correct)
    assert _errors(error) == {"correct": ["Choose the correct option."]}


@pytest.mark.django_db
def test_subject_must_be_the_teachers(school) -> None:
    with pytest.raises(ValidationError) as error:
        add_question(school, subject=school.physics)
    assert _errors(error) == {"subject": ["The teacher does not teach this subject."]}


@pytest.mark.django_db
def test_edit_replaces_the_options(school) -> None:
    question = add_question(school)
    add_question(school, question, options=("True", "False"), correct=0, text="1=1")
    question.refresh_from_db()
    assert question.text == "1=1"
    assert _options(question) == [(1, "True", True), (2, "False", False)]
    add_question(school, question, kind=QuestionKind.SHORT, options=(), correct=None)
    assert _options(question) == []


@pytest.mark.django_db
def test_edit_keeps_the_teacher(school) -> None:
    question = add_question(school)
    with pytest.raises(ValidationError) as error:
        add_question(school, question, teacher=school.teacher_2)
    assert "teacher" in _errors(error)


# Pages


@pytest.mark.django_db
def test_pages_refuse_other_roles(school) -> None:
    question = add_question(school)
    urls = [
        LIST_URL,
        ADD_URL,
        reverse("teacher:question_edit", kwargs={"pk": question.pk}),
    ]
    for role in ROLES - {Role.TEACHER}:
        user = make_user(
            email=f"{role}@example.com", role=role, institute=school.math.institute
        )
        client = signed_in(user)
        for url in urls:
            assert client.get(url).status_code == 403, (role, url)
        delete = reverse("teacher:question_delete", kwargs={"pk": question.pk})
        assert client.post(delete).status_code == 403, role


@pytest.mark.django_db
def test_other_teacher_and_institute_get_404(school) -> None:
    question = add_question(school)
    edit = reverse("teacher:question_edit", kwargs={"pk": question.pk})
    delete = reverse("teacher:question_delete", kwargs={"pk": question.pk})
    for user in (school.teacher_2.user, school.teacher_b.user):
        client = signed_in(user)
        assert client.get(edit).status_code == 404
        assert client.post(delete).status_code == 404
    assert Question.unscoped.filter(pk=question.pk).exists()  # unscoped: test


@pytest.mark.django_db
def test_list_empty_then_rows_and_filters(school) -> None:
    client = signed_in(school.teacher_1.user)
    html = client.get(LIST_URL).content.decode()
    assert "No questions yet." in html
    assert f'href="{ADD_URL}"' in html
    assert f'href="{LIST_URL}"' in html  # the menu link is built

    add_question(school)
    add_question(
        school, kind=QuestionKind.SHORT, options=(), correct=None, text="Explain 0."
    )
    html = client.get(LIST_URL).content.decode()
    row = table_row(html, "What is half of 10?")
    assert cell(row, "answer") == ["2.", "5"]
    assert cell(row, "kind") == ["MCQ"]
    short = table_row(html, "Explain 0.")
    assert cell(short, "answer") == ["Marked", "by", "the", "teacher"]

    html = client.get(LIST_URL, {"kind": "short"}).content.decode()
    assert "Explain 0." in html and "half of 10" not in html
    html = client.get(LIST_URL, {"q": "HALF"}).content.decode()
    assert "half of 10" in html and "Explain 0." not in html


@pytest.mark.django_db
def test_add_mcq_skips_empty_boxes(school) -> None:
    client = signed_in(school.teacher_1.user)
    html = client.get(ADD_URL).content.decode()
    assert select_values(html, "subject") == ["", str(school.math.pk)]
    response = client.post(ADD_URL, _form(school))
    assert response.status_code == 302
    assert response["Location"] == LIST_URL
    # unscoped: test assertion outside a tenant context.
    question = Question.unscoped.get()
    assert question.teacher == school.teacher_1 and question.marks == 3
    assert _options(question) == [(1, "4", False), (2, "7", True), (3, "9", False)]


@pytest.mark.django_db
def test_add_refuses_an_empty_correct_option(school) -> None:
    client = signed_in(school.teacher_1.user)
    response = client.post(ADD_URL, _form(school, correct="2"))
    assert response.status_code == 200
    assert "The correct option is empty." in response.content.decode()
    response = client.post(ADD_URL, _form(school, correct=""))
    assert "Choose the correct option." in response.content.decode()
    assert not Question.unscoped.exists()  # unscoped: test assertion


@pytest.mark.django_db
def test_add_short_answer_ignores_the_option_boxes(school) -> None:
    client = signed_in(school.teacher_1.user)
    response = client.post(ADD_URL, _form(school, kind="short", text="Define a prime."))
    assert response.status_code == 302
    question = Question.unscoped.get()  # unscoped: test assertion
    assert question.kind == QuestionKind.SHORT
    assert _options(question) == []


@pytest.mark.django_db
def test_edit_shows_and_saves_the_question(school) -> None:
    question = add_question(school)
    url = reverse("teacher:question_edit", kwargs={"pk": question.pk})
    client = signed_in(school.teacher_1.user)
    html = client.get(url).content.decode()
    assert 'name="option_2" value="5"' in html
    assert 'value="2" id="id_correct_1" checked' in html
    response = client.post(url, _form(school, text="Changed?"))
    assert response.status_code == 302
    question.refresh_from_db()
    assert question.text == "Changed?"


@pytest.mark.django_db
def test_delete_question(school) -> None:
    question = add_question(school)
    url = reverse("teacher:question_delete", kwargs={"pk": question.pk})
    client = signed_in(school.teacher_1.user)
    assert client.get(url).status_code == 405
    html = client.get(LIST_URL).content.decode()
    assert url in html  # the confirm dialog posts here
    assert client.post(url).status_code == 302
    assert not Question.unscoped.exists()  # unscoped: test assertion
    assert not QuestionOption.unscoped.exists()  # unscoped: test assertion
