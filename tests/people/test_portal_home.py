"""Portal home pages for teachers, students and guardians (roadmap R4c)."""

from __future__ import annotations

from datetime import datetime

import pytest
from apps.core.roles import Role
from apps.people.home import greeting, guardian_home, student_home, teacher_home
from django.test import Client
from django.urls import reverse

from tests.conftest import make_user
from tests.school import link_teacher


@pytest.mark.parametrize(
    ("hour", "text"),
    [
        (0, "Good morning"),
        (11, "Good morning"),
        (12, "Good afternoon"),
        (16, "Good afternoon"),
        (17, "Good evening"),
        (23, "Good evening"),
    ],
)
def test_greeting_follows_the_hour(hour, text) -> None:
    assert greeting(datetime(2026, 10, 9, hour, 30)) == text


@pytest.mark.django_db
def test_teacher_home_counts_own_batches_subjects_and_students(school) -> None:
    link_teacher(school.teacher_1, {school.morning: [school.math, school.physics]})

    data = teacher_home(school.teacher_1.user)

    assert data.profile == school.teacher_1
    assert data.pairs == ["Morning: Math", "Morning: Physics"]
    assert (data.batch_count, data.subject_count) == (1, 2)
    assert data.student_count == 1  # student_1 only; Evening is not theirs


@pytest.mark.django_db
def test_teacher_without_batches_has_zero_counts(school) -> None:
    data = teacher_home(school.teacher_idle.user)

    assert data.pairs == []
    assert (data.student_count, data.batch_count, data.subject_count) == (0, 0, 0)


@pytest.mark.django_db
def test_student_home_lists_own_pairs_only(school) -> None:
    data = student_home(school.student_2.user)

    assert data.profile == school.student_2
    assert data.pairs == ["Evening: Physics"]


@pytest.mark.django_db
def test_guardian_home_lists_linked_children_only(school) -> None:
    data = guardian_home(school.guardian_1.user)

    assert data.children == [school.student_1]


@pytest.mark.django_db
def test_other_institute_people_never_show(school) -> None:
    assert teacher_home(school.teacher_b.user).student_count == 1  # student_b
    assert "Morning: Math" in teacher_home(school.teacher_b.user).pairs
    assert school.student_1 not in guardian_home(school.guardian_2.user).children


def _page(user, name: str) -> str:
    client = Client()
    client.force_login(user)
    response = client.get(reverse(name))
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
def test_teacher_home_shows_welcome_pairs_up_next_and_stats(school) -> None:
    page = _page(school.teacher_1.user, "teacher:home")

    assert "Good " in page and "hero-banner" in page
    assert ">Morning: Math</li>" in page
    assert "Evening: Physics" not in page
    assert ">No lectures yet<" in page
    assert ">My students<" in page and ">Batches<" in page
    # "Up next" comes before the stat cards (FEATURES 13).
    assert page.index("Up next") < page.index("stat-card")


@pytest.mark.django_db
def test_student_home_shows_code_and_pairs(school) -> None:
    page = _page(school.student_1.user, "student:home")

    assert school.student_1.student_code in page
    assert ">Morning: Physics</li>" in page
    assert ">Up next<" in page
    assert "stat-card" not in page  # its KPIs come with later phases


@pytest.mark.django_db
def test_guardian_home_shows_children_and_upcoming_classes(school) -> None:
    page = _page(school.guardian_1.user, "guardian:home")

    assert ">Your children<" in page
    assert school.student_1.student_code in page
    assert school.student_2.student_code not in page
    assert ">Upcoming classes<" in page


@pytest.mark.django_db
def test_guardian_without_children_sees_what_to_do(institute_a) -> None:
    user = make_user(email="g@example.com", role=Role.GUARDIAN, institute=institute_a)

    page = _page(user, "guardian:home")

    assert "Contact the institute office." in page


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "name"),
    [
        (Role.TEACHER, "student:home"),
        (Role.STUDENT, "teacher:home"),
        (Role.INSTITUTE_ADMIN, "guardian:home"),
        (Role.GUARDIAN, "teacher:home"),
    ],
)
def test_other_roles_get_403(institute_a, role, name) -> None:
    client = Client()
    client.force_login(
        make_user(email="x@example.com", role=role, institute=institute_a)
    )

    assert client.get(reverse(name)).status_code == 403
