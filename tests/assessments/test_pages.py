"""Roadmap 5.1 pages: teacher Assignments, Add / Edit, the answers and the
grade page; student Assignments and the assignment page."""

from __future__ import annotations

import pytest
from apps.assessments.models import Assignment, Submission
from apps.core.roles import Role
from django.urls import reverse
from django.utils import timezone

from tests.assessments.conftest import add_assignment, answer, close, grade, in_days
from tests.conftest import cell, make_user, table_row
from tests.lectures.conftest import select_values, signed_in
from tests.school import link_teacher

TEACHER_LIST = reverse("teacher:assignment_list")
TEACHER_ADD = reverse("teacher:assignment_create")
STUDENT_LIST = reverse("student:assignment_list")
ROLES = {
    Role.INSTITUTE_ADMIN,
    Role.SUB_ADMIN,
    Role.TEACHER,
    Role.STUDENT,
    Role.GUARDIAN,
}


def _html(client, url: str, **params) -> str:
    response = client.get(url, params)
    assert response.status_code == 200
    return response.content.decode()


def _urls(assignment: Assignment, submission: Submission | None = None) -> dict:
    pk = assignment.pk
    urls = {
        "detail": reverse("teacher:assignment_detail", kwargs={"pk": pk}),
        "edit": reverse("teacher:assignment_edit", kwargs={"pk": pk}),
        "student": reverse("student:assignment_detail", kwargs={"pk": pk}),
    }
    if submission is not None:
        urls["grade"] = reverse(
            "teacher:assignment_grade",
            kwargs={"pk": pk, "submission_pk": submission.pk},
        )
    return urls


def _form(school, **fields) -> dict[str, str]:
    due = timezone.localtime(in_days(3), timezone.get_fixed_timezone(300))
    values = {
        "title": "Ratio practice",
        "instructions": "Solve questions 1 to 5.",
        "batch_subject": f"{school.morning.pk}:{school.math.pk}",
        "total_marks": "20",
        "due_date": due.date().isoformat(),
        "due_time": "18:00",
    }
    values.update(fields)
    return values


# Access


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("url", "allowed"),
    [(TEACHER_LIST, Role.TEACHER), (TEACHER_ADD, Role.TEACHER)]
    + [(STUDENT_LIST, Role.STUDENT)],
)
def test_list_pages_refuse_other_roles(institute_a, url, allowed) -> None:
    for role in ROLES - {allowed}:
        user = make_user(email=f"{role}@example.com", role=role, institute=institute_a)
        assert signed_in(user).get(url).status_code == 403, role


@pytest.mark.django_db
def test_object_pages_refuse_other_roles(school) -> None:
    assignment = add_assignment(school)
    urls = _urls(assignment, answer(assignment, school.student_1))
    institute = school.morning.institute
    for role in ROLES - {Role.TEACHER}:
        user = make_user(email=f"{role}@example.com", role=role, institute=institute)
        for name in ("detail", "edit", "grade"):
            assert signed_in(user).get(urls[name]).status_code == 403, (role, name)
    for role in ROLES - {Role.STUDENT}:
        user = make_user(email=f"x-{role}@example.com", role=role, institute=institute)
        assert signed_in(user).get(urls["student"]).status_code == 403, role


@pytest.mark.django_db
def test_other_teacher_and_institute_get_404(school) -> None:
    assignment = add_assignment(school)
    urls = _urls(assignment, answer(assignment, school.student_1))
    for user in (school.teacher_2.user, school.teacher_b.user):
        client = signed_in(user)
        for name in ("detail", "edit", "grade"):
            assert client.get(urls[name]).status_code == 404, (user, name)
    for user in (school.student_2.user, school.student_b.user):
        assert signed_in(user).get(urls["student"]).status_code == 404


@pytest.mark.django_db
def test_grade_url_needs_the_matching_assignment(school) -> None:
    first = add_assignment(school)
    second = add_assignment(school, title="Second")
    row = answer(first, school.student_1)
    url = reverse(
        "teacher:assignment_grade",
        kwargs={"pk": second.pk, "submission_pk": row.pk},
    )
    assert signed_in(school.teacher_1.user).get(url).status_code == 404


# Teacher


@pytest.mark.django_db
def test_teacher_list_empty_then_rows(school) -> None:
    client = signed_in(school.teacher_1.user)
    html = _html(client, TEACHER_LIST)
    assert "No assignments yet." in html
    assert f'href="{TEACHER_ADD}"' in html

    assignment = add_assignment(school)
    grade(answer(assignment, school.student_1), "8")
    add_assignment(school, title="Second sheet")
    html = _html(client, TEACHER_LIST)
    row = table_row(html, "Fractions worksheet")
    assert cell(row, "submitted") == ["1", "/", "1"]
    assert cell(row, "status") == ["Open"]
    assert cell(row, "batch") == ["Morning"]
    assert cell(table_row(html, "Second sheet"), "submitted") == ["0", "/", "1"]


@pytest.mark.django_db
def test_teacher_list_shows_answers_to_grade(school) -> None:
    assignment = close(add_assignment(school), days_ago=0.0001)
    Submission.unscoped.create(  # unscoped: test set-up, a closed assignment
        institute=assignment.institute,
        assignment=assignment,
        student=school.student_1,
        answer="Sent in time.",
        submitted_at=in_days(-1),
    )
    html = _html(signed_in(school.teacher_1.user), TEACHER_LIST)
    assert cell(table_row(html, "Fractions worksheet"), "status") == [
        "Closed",
        "1",
        "to",
        "grade",
    ]


@pytest.mark.django_db
def test_teacher_list_filters(school) -> None:
    link_teacher(school.teacher_1, {school.morning: [school.math, school.physics]})
    add_assignment(school)
    add_assignment(school, title="Optics", subject=school.physics)
    client = signed_in(school.teacher_1.user)
    html = _html(client, TEACHER_LIST, subject=school.physics.pk)
    assert "Optics" in html and "Fractions worksheet" not in html
    assert select_values(html, "batch") == ["", str(school.morning.pk)]


@pytest.mark.django_db
def test_add_assignment(school) -> None:
    client = signed_in(school.teacher_1.user)
    html = _html(client, TEACHER_ADD)
    assert select_values(html, "batch_subject") == [
        "",
        f"{school.morning.pk}:{school.math.pk}",
    ]
    response = client.post(TEACHER_ADD, _form(school))
    # unscoped: test assertion outside a tenant context.
    saved = Assignment.unscoped.get(title="Ratio practice")
    assert response.status_code == 302
    assert response["Location"] == _urls(saved)["detail"]
    assert saved.teacher == school.teacher_1
    assert saved.total_marks == 20
    local = timezone.localtime(saved.due_at, timezone.get_fixed_timezone(300))
    assert local.strftime("%H:%M") == "18:00"  # the teacher's zone, Karachi


@pytest.mark.django_db
def test_add_refuses_a_subject_the_teacher_does_not_teach(school) -> None:
    client = signed_in(school.teacher_1.user)
    data = _form(school, batch_subject=f"{school.evening.pk}:{school.physics.pk}")
    response = client.post(TEACHER_ADD, data)
    assert response.status_code == 200
    assert "Select a valid choice" in response.content.decode()
    assert not Assignment.unscoped.exists()  # unscoped: test assertion


@pytest.mark.django_db
def test_add_refuses_a_past_due_time(school) -> None:
    client = signed_in(school.teacher_1.user)
    response = client.post(TEACHER_ADD, _form(school, due_date="2020-01-01"))
    assert "Choose a due time in the future." in response.content.decode()


@pytest.mark.django_db
def test_edit_assignment(school) -> None:
    assignment = add_assignment(school)
    urls = _urls(assignment)
    client = signed_in(school.teacher_1.user)
    html = _html(client, urls["edit"])
    assert 'value="Fractions worksheet"' in html
    response = client.post(urls["edit"], _form(school, title="Renamed sheet"))
    assert response.status_code == 302
    assignment.refresh_from_db()
    assert assignment.title == "Renamed sheet"


@pytest.mark.django_db
def test_detail_lists_every_expected_student(school) -> None:
    assignment = add_assignment(school)
    row = answer(assignment, school.student_1, "Line one.\nLine two.")
    html = _html(signed_in(school.teacher_1.user), _urls(assignment, row)["detail"])
    student_row = table_row(html, str(school.student_1))
    assert cell(student_row, "status") == ["Submitted"]
    assert cell(student_row, "marks") == ["-"]
    assert _urls(assignment, row)["grade"] in student_row
    assert "Answer all questions.\nShow your working." in html


@pytest.mark.django_db
def test_grade_an_answer(school) -> None:
    assignment = add_assignment(school)
    row = answer(assignment, school.student_1, "<b>Bold</b> answer.")
    urls = _urls(assignment, row)
    client = signed_in(school.teacher_1.user)
    html = _html(client, urls["grade"])
    assert "&lt;b&gt;Bold&lt;/b&gt; answer." in html  # escaped
    assert "Marks (out of 10)" in html

    response = client.post(urls["grade"], {"marks": "11", "feedback": ""})
    assert response.status_code == 200
    assert "less than or equal to 10" in response.content.decode()

    response = client.post(urls["grade"], {"marks": "7.5", "feedback": "Good."})
    assert response.status_code == 302
    assert response["Location"] == urls["detail"]
    row.refresh_from_db()
    assert str(row.marks) == "7.5"
    assert row.graded_by == school.teacher_1.user
    html = _html(client, urls["detail"])
    assert cell(table_row(html, str(school.student_1)), "marks") == ["7.5", "/", "10"]


@pytest.mark.django_db
def test_teacher_dashboard_counts_answers_to_grade(school) -> None:
    assignment = add_assignment(school)
    answer(assignment, school.student_1)
    html = _html(signed_in(school.teacher_1.user), reverse("teacher:home"))
    assert "Answers to grade" in html
    assert f'href="{TEACHER_LIST}"' in html  # the menu link is built


# Student


@pytest.mark.django_db
def test_student_list_statuses_and_marks(old_school) -> None:
    school = old_school
    graded = add_assignment(school, title="Graded one")
    grade(answer(graded, school.student_1), "9", "Well done.")
    add_assignment(school, title="Pending one")
    close(add_assignment(school, title="Missed one"))
    client = signed_in(school.student_1.user)
    html = _html(client, STUDENT_LIST)
    assert cell(table_row(html, "Graded one"), "status") == ["Graded"]
    assert cell(table_row(html, "Graded one"), "marks") == ["9", "/", "10"]
    assert cell(table_row(html, "Pending one"), "status") == ["Pending"]
    assert cell(table_row(html, "Missed one"), "status") == ["Missed"]

    html = _html(client, STUDENT_LIST, status="missed")
    assert "Missed one" in html and "Pending one" not in html
    html = _html(client, STUDENT_LIST, status="nonsense")
    assert "Pending one" in html


@pytest.mark.django_db
def test_student_submits_and_changes_an_answer(school) -> None:
    assignment = add_assignment(school)
    url = _urls(assignment)["student"]
    client = signed_in(school.student_1.user)
    html = _html(client, url)
    assert "Submit answer" in html
    assert "Answer all questions.\nShow your working." in html

    response = client.post(url, {"answer": "Half is 0.5."})
    assert response.status_code == 302
    html = _html(client, url)
    assert "Save answer" in html and "Half is 0.5." in html

    client.post(url, {"answer": "Half is 1/2."})
    # unscoped: test assertion outside a tenant context.
    assert Submission.unscoped.get().answer == "Half is 1/2."


@pytest.mark.django_db
def test_student_sees_grade_and_no_form(school) -> None:
    assignment = add_assignment(school)
    grade(answer(assignment, school.student_1, "My work."), "6.5", "Check step 2.")
    html = _html(signed_in(school.student_1.user), _urls(assignment)["student"])
    assert "6.5 / 10" in html
    assert "Check step 2." in html
    assert 'name="answer"' not in html


@pytest.mark.django_db
def test_student_cannot_answer_after_the_due_time(old_school) -> None:
    school = old_school
    assignment = close(add_assignment(school))
    url = _urls(assignment)["student"]
    client = signed_in(school.student_1.user)
    html = _html(client, url)
    assert "No answer was sent." in html
    assert 'name="answer"' not in html
    response = client.post(url, {"answer": "Too late."})
    assert response.status_code == 302
    assert not Submission.unscoped.exists()  # unscoped: test assertion


@pytest.mark.django_db
def test_student_enrolled_after_the_due_time_goes_back_to_the_list(school) -> None:
    """for_user shows the batch's assignments; one due before the student
    joined is not theirs."""
    assignment = close(add_assignment(school))
    url = _urls(assignment)["student"]
    response = signed_in(school.student_1.user).get(url)
    assert response.status_code == 302
    assert response["Location"] == STUDENT_LIST
