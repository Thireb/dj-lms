"""Student "My lectures" and guardian "Lectures schedule" (roadmap 3.3,
SPEC 3)."""

from __future__ import annotations

import re

import pytest
from apps.core.roles import Role
from apps.lectures.models import Lecture
from django.urls import reverse
from django.utils import timezone

from tests.conftest import cell, make_user, table_row
from tests.lectures.conftest import add_lecture, put_at, select_values, signed_in
from tests.people.conftest import student
from tests.school import link_guardian, link_student

STUDENT_URL = reverse("student:lecture_list")
GUARDIAN_URL = reverse("guardian:lecture_schedule")


def _evening(school, **fields) -> Lecture:
    return add_lecture(
        school,
        title="Evening physics",
        teacher=school.teacher_2,
        batch=school.evening,
        subjects=[school.physics],
        **fields,
    )


def _html(user, url: str, **params) -> str:
    response = signed_in(user).get(url, params)
    assert response.status_code == 200
    return response.content.decode()


# Access


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("url", "allowed"),
    [(STUDENT_URL, Role.STUDENT), (GUARDIAN_URL, Role.GUARDIAN)],
)
def test_other_roles_get_403(institute_a, url, allowed) -> None:
    others = {Role.INSTITUTE_ADMIN, Role.SUB_ADMIN, Role.TEACHER, Role.STUDENT}
    for role in (others | {Role.GUARDIAN}) - {allowed}:
        client = signed_in(
            make_user(email=f"{role}@example.com", role=role, institute=institute_a)
        )
        assert client.get(url).status_code == 403, role


# Student


@pytest.mark.django_db
def test_student_sees_own_lectures_read_only(school) -> None:
    add_lecture(school, title="Algebra basics")
    _evening(school)

    html = _html(school.student_1.user, STUDENT_URL)

    row = table_row(html, "Algebra basics")
    assert "Evening physics" not in html
    assert cell(row, "subjects") == ["Math"]
    assert cell(row, "teacher") == str(school.teacher_1).split()
    assert cell(row, "status") == ["Scheduled"]
    assert "lecture_edit" not in html and "/edit/" not in html
    assert "cell-batch" not in html and "cell-mode" not in html
    assert re.search(rf'href="{STUDENT_URL}"[^>]*aria-current="page"', html)


@pytest.mark.django_db
def test_student_tabs_and_subject_filter(school) -> None:
    past = put_at(
        add_lecture(school, title="Old algebra"),
        timezone.now() - timezone.timedelta(days=2),
    )

    upcoming = _html(school.student_1.user, STUDENT_URL)
    old = _html(school.student_1.user, STUDENT_URL, show="past")

    assert "No upcoming lectures." in upcoming
    assert past.title in old
    assert select_values(old, "subject") == [
        "",
        str(school.math.pk),
        str(school.physics.pk),
    ]
    assert '<select name="batch"' not in old
    assert '<select name="status"' not in old


@pytest.mark.django_db
def test_student_with_no_lectures_sees_a_plain_empty_state(school) -> None:
    html = _html(school.student_1.user, STUDENT_URL)

    assert "No lectures yet." in html
    assert "Lectures for your batches and subjects show here." in html
    assert "Create" not in html.split("<main", 1)[-1].split("</main>")[0]


@pytest.mark.django_db
def test_other_institute_student_sees_nothing(school) -> None:
    add_lecture(school, title="Algebra basics")

    html = _html(school.student_b.user, STUDENT_URL)

    assert "Algebra basics" not in html


# Guardian


@pytest.mark.django_db
def test_guardian_sees_the_child_lectures(school) -> None:
    add_lecture(school, title="Algebra basics")
    _evening(school)

    html = _html(school.guardian_1.user, GUARDIAN_URL)

    assert table_row(html, "Algebra basics")
    assert "Evening physics" not in html
    assert f"Lectures for {school.student_1}." in html
    assert '<select name="child"' not in html  # one child, no choice
    assert re.search(rf'href="{GUARDIAN_URL}"[^>]*aria-current="page"', html)


@pytest.fixture
def two_children(school):
    """guardian_1 also becomes the guardian of student_2."""
    link_guardian(school.student_2, "g1-a@example.com")
    return school


@pytest.mark.django_db
def test_guardian_with_two_children_chooses_one(two_children) -> None:
    school = two_children
    add_lecture(school, title="Algebra basics")
    _evening(school)
    guardian = school.guardian_1.user
    first, second = sorted(
        [school.student_1, school.student_2],
        key=lambda child: (child.user.first_name, child.user.last_name, child.pk),
    )
    titles = {
        school.student_1.pk: "Algebra basics",
        school.student_2.pk: "Evening physics",
    }

    default = _html(guardian, GUARDIAN_URL)
    chosen = _html(guardian, GUARDIAN_URL, child=second.pk)

    assert select_values(default, "child") == [str(first.pk), str(second.pk)]
    assert titles[first.pk] in default and titles[second.pk] not in default
    assert titles[second.pk] in chosen and titles[first.pk] not in chosen
    # The tabs keep the chosen child.
    assert f"child={second.pk}" in chosen.split('aria-label="Lecture lists"')[1]


@pytest.mark.django_db
def test_guardian_subjects_are_the_child_subjects(two_children) -> None:
    school = two_children

    html = _html(school.guardian_1.user, GUARDIAN_URL, child=school.student_2.pk)

    assert select_values(html, "subject") == ["", str(school.physics.pk)]


@pytest.mark.django_db
def test_guardian_cannot_choose_another_student(school, institute_a) -> None:
    """An unlinked student in the same batch falls back to the own child."""
    other = student(institute_a, "other-s@example.com")
    link_student(other, {school.evening: [school.physics]})
    _evening(school)

    html = _html(school.guardian_1.user, GUARDIAN_URL, child=other.pk)

    assert "Evening physics" not in html
    assert f"Lectures for {school.student_1}." in html


@pytest.mark.django_db
def test_guardian_with_no_children(institute_a) -> None:
    guardian = make_user(
        email="lonely-g@example.com", role=Role.GUARDIAN, institute=institute_a
    )

    html = _html(guardian, GUARDIAN_URL)

    assert "No children are linked to this account yet." in html


@pytest.mark.django_db
def test_guardian_clear_keeps_the_chosen_child(two_children) -> None:
    school = two_children
    child = school.student_2.pk

    plain = _html(school.guardian_1.user, GUARDIAN_URL, child=child)
    filtered = _html(
        school.guardian_1.user, GUARDIAN_URL, child=child, subject=school.physics.pk
    )

    assert ">Clear<" not in plain
    assert f'href="?child={child}" class="btn btn-ghost">Clear<' in filtered
