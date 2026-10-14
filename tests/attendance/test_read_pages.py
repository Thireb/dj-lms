"""Roadmap 4.2 pages: student "My attendance", guardian "Class attendance"
(with the header child switcher, backlog LC7) and admin "Student
attendance history"."""

from __future__ import annotations

import pytest
from apps.attendance.views import AdminStudentAttendancePage
from apps.core.roles import Role
from django.test import RequestFactory
from django.urls import reverse

from tests.attendance.conftest import finished, mark
from tests.conftest import cell, make_user, table_row
from tests.lectures.conftest import select_values, signed_in
from tests.people.conftest import student
from tests.school import link_guardian, link_student

STUDENT_URL = reverse("student:attendance")
GUARDIAN_URL = reverse("guardian:attendance")
ADMIN_URL = reverse("admin:student_attendance_history")
CHOOSE_URL = reverse("guardian:choose_child")


def _html(client, url: str, **params) -> str:
    response = client.get(url, params)
    assert response.status_code == 200
    return response.content.decode()


def _evening(school, **fields):
    return finished(
        school,
        title="Evening physics",
        teacher=school.teacher_2,
        batch=school.evening,
        subjects=[school.physics],
        **fields,
    )


# Access


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("url", "allowed"),
    [
        (STUDENT_URL, {Role.STUDENT}),
        (GUARDIAN_URL, {Role.GUARDIAN}),
        (ADMIN_URL, {Role.INSTITUTE_ADMIN, Role.SUB_ADMIN}),
        (CHOOSE_URL, {Role.GUARDIAN}),
    ],
)
def test_other_roles_get_403(institute_a, url, allowed) -> None:
    roles = {
        Role.INSTITUTE_ADMIN,
        Role.SUB_ADMIN,
        Role.TEACHER,
        Role.STUDENT,
        Role.GUARDIAN,
    }
    for role in roles - allowed:
        user = make_user(email=f"{role}@example.com", role=role, institute=institute_a)
        assert signed_in(user).get(url).status_code == 403, role


@pytest.mark.django_db
def test_sub_admin_needs_the_people_menu(institute_a) -> None:
    user = make_user(
        email="sub@example.com", role=Role.SUB_ADMIN, institute=institute_a
    )
    # The test middleware gives a sub-admin only "dashboards".
    assert signed_in(user).get(ADMIN_URL).status_code == 403
    user.allowed_menus = ["people"]
    request = RequestFactory().get(ADMIN_URL)
    request.user = user
    request.institute = institute_a
    assert AdminStudentAttendancePage.as_view()(request).status_code == 200


# Student


@pytest.mark.django_db
def test_student_sees_own_marks_and_percent(old_school) -> None:
    school = old_school
    taken = finished(school, title="Taken", days_ago=2)
    finished(school, title="Untaken", days_ago=1)
    _evening(school)
    mark(taken, {school.student_1: "partial"})

    html = _html(signed_in(school.student_1.user), STUDENT_URL)

    assert cell(table_row(html, "Taken"), "status") == ["Partial"]
    assert cell(table_row(html, "Untaken"), "status") == ["Not", "marked"]
    assert "Evening physics" not in html
    # (0.5 partial) / 2 classes = 25%
    assert ">25%<" in html
    assert "2 finished classes" in html
    assert "1 not marked" in html
    assert "student:attendance" not in html  # menu shows a URL, not a name
    assert f'href="{STUDENT_URL}"' in html


@pytest.mark.django_db
def test_student_with_no_classes_sees_a_dash(old_school) -> None:
    html = _html(signed_in(old_school.student_1.user), STUDENT_URL)
    assert "No finished classes match these filters." in html
    assert "0 finished classes" in html


@pytest.mark.django_db
def test_student_subject_filter_lists_own_subjects(old_school) -> None:
    school = old_school
    html = _html(signed_in(school.student_1.user), STUDENT_URL)
    assert select_values(html, "subject") == [
        "",
        str(school.math.pk),
        str(school.physics.pk),
    ]
    html = _html(signed_in(school.student_2.user), STUDENT_URL)
    assert select_values(html, "subject") == ["", str(school.physics.pk)]


@pytest.mark.django_db
def test_bad_dates_are_ignored(old_school) -> None:
    school = old_school
    finished(school, title="Taken")
    html = _html(
        signed_in(school.student_1.user),
        STUDENT_URL,
        date_from="not-a-date",
        date_to="9999-12-31",
    )
    assert table_row(html, "Taken")


# Guardian and the child switcher


@pytest.fixture
def two_children(old_school):
    """guardian_1 also becomes the guardian of student_2."""
    link_guardian(old_school.student_2, "g1-a@example.com")
    return old_school


@pytest.mark.django_db
def test_guardian_sees_the_child_without_a_switcher(old_school) -> None:
    school = old_school
    finished(school, title="Morning math")
    _evening(school)

    html = _html(signed_in(school.guardian_1.user), GUARDIAN_URL)

    assert table_row(html, "Morning math")
    assert "Evening physics" not in html
    assert f"Finished classes of {school.student_1}." in html
    assert "child-switcher" not in html


@pytest.mark.django_db
def test_guardian_switches_child_for_every_page(two_children) -> None:
    school = two_children
    finished(school, title="Morning math")
    _evening(school)
    client = signed_in(school.guardian_1.user)
    first, second = sorted(
        [school.student_1, school.student_2],
        key=lambda child: (child.user.first_name, child.user.last_name, child.pk),
    )
    titles = {
        school.student_1.pk: "Morning math",
        school.student_2.pk: "Evening physics",
    }

    before = _html(client, GUARDIAN_URL)
    response = client.post(CHOOSE_URL, {"child": second.pk, "next": GUARDIAN_URL})
    after = _html(client, GUARDIAN_URL)
    home = _html(client, reverse("guardian:home"))

    assert response["Location"] == GUARDIAN_URL
    assert select_values(before, "child") == [str(first.pk), str(second.pk)]
    assert titles[first.pk] in before and titles[second.pk] not in before
    assert titles[second.pk] in after and titles[first.pk] not in after
    assert f'<option value="{second.pk}" selected>' in after
    assert f'<option value="{second.pk}" selected>' in home
    assert 'name="next" value="/guardian/attendance/"' in after


@pytest.mark.django_db
def test_guardian_cannot_choose_an_unlinked_student(two_children, institute_a) -> None:
    school = two_children
    other = student(institute_a, "other-s@example.com")
    link_student(other, {school.evening: [school.physics]})
    client = signed_in(school.guardian_1.user)
    client.post(CHOOSE_URL, {"child": school.student_2.pk})

    response = client.post(CHOOSE_URL, {"child": other.pk})

    assert client.session["guardian_child_id"] == school.student_2.pk
    assert response["Location"] == reverse("guardian:home")
    page = _html(client, GUARDIAN_URL)
    assert f"Finished classes of {school.student_2}." in page
    assert f"Finished classes of {other}." not in page


@pytest.mark.django_db
@pytest.mark.parametrize(
    "wanted",
    [
        "https://evil.example.com/guardian/",
        "//evil.example.com/guardian/",
        "/admin/",
        "",
    ],
)
def test_switcher_goes_back_only_to_a_guardian_page(two_children, wanted) -> None:
    school = two_children
    response = signed_in(school.guardian_1.user).post(
        CHOOSE_URL, {"child": school.student_2.pk, "next": wanted}
    )
    assert response["Location"] == reverse("guardian:home")


@pytest.mark.django_db
def test_switcher_is_a_csrf_form(two_children) -> None:
    school = two_children
    html = _html(signed_in(school.guardian_1.user), GUARDIAN_URL)
    form = html.split('class="child-switcher')[1].split("</form>")[0]
    assert f'action="{CHOOSE_URL}"' in html
    assert 'name="csrfmiddlewaretoken"' in form
    assert '<label for="child-switcher" class="sr-only">Child</label>' in form


@pytest.mark.django_db
def test_guardian_with_no_children(institute_a) -> None:
    guardian = make_user(
        email="lonely-g@example.com", role=Role.GUARDIAN, institute=institute_a
    )
    html = _html(signed_in(guardian), GUARDIAN_URL)
    assert "No children are linked to this account yet." in html


# Admin


@pytest.mark.django_db
def test_admin_chooses_a_student(old_school, admin_client) -> None:
    school = old_school
    lecture = finished(school, title="Morning math")
    mark(lecture, {school.student_1: "late"})

    empty = _html(admin_client, ADMIN_URL)
    chosen = _html(admin_client, ADMIN_URL, student=school.student_1.pk)

    assert "Choose a student." in empty
    assert 'name="subject"' not in empty
    # Student pks are one sequence, so another institute's pk cannot match.
    assert str(school.student_b.pk) not in select_values(empty, "student")
    assert cell(table_row(chosen, "Morning math"), "status") == ["Late"]
    assert ">100%<" in chosen
    assert f"Finished classes of {school.student_1}." in chosen


@pytest.mark.django_db
def test_admin_cannot_open_another_institute_student(old_school, admin_client) -> None:
    html = _html(admin_client, ADMIN_URL, student=old_school.student_b.pk)
    assert "Choose a student." in html


@pytest.mark.django_db
def test_all_students_row_links_to_the_history(old_school, admin_client) -> None:
    school = old_school
    html = _html(admin_client, reverse("admin:student_list"))
    assert f"{ADMIN_URL}?student={school.student_1.pk}" in html
    assert f'aria-label="Attendance history of {school.student_1}"' in html
