"""Query budgets for the dashboards (redesign audit RA8).

Each page is loaded with more people than it lists, so a query per row
(N+1) breaks the budget. Raise a budget only with a reason in the commit.
"""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from django.test import Client
from django.urls import reverse

from tests.attendance.conftest import backdate_enrolments, finished
from tests.conftest import make_user
from tests.lectures.conftest import add_lecture, soon
from tests.people.conftest import student
from tests.school import link_guardian, link_student


@pytest.fixture
def busy_school(school, institute_a):
    for number in range(8):
        extra = student(institute_a, f"extra{number}@example.com")
        link_student(extra, {school.morning: [school.math, school.physics]})
    sibling = student(institute_a, "sibling@example.com")
    link_student(sibling, {school.evening: [school.physics]})
    link_guardian(sibling, "g1-a@example.com")
    # Lectures for the up-next cards and lists: more than one, so a query
    # per lecture shows.
    for days in (1, 2, 3):
        add_lecture(school, title=f"Math {days}", starts_at=soon(days=days))
        add_lecture(
            school,
            title=f"Physics {days}",
            teacher=school.teacher_2,
            batch=school.evening,
            subjects=[school.physics],
            starts_at=soon(days=days, hour=12),
        )
    # Finished lectures with students and no marks, for the attendance
    # numbers (a query per lecture shows).
    backdate_enrolments()
    for days in (1, 2, 3):
        # Made in a free slot first; finished() then moves it into the past.
        finished(
            school, title=f"Done {days}", days_ago=days, starts_at=soon(days=10 + days)
        )
    return school


def _client(user) -> Client:
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_admin_dashboard_query_budget(
    busy_school, institute_a, django_assert_max_num_queries
) -> None:
    admin = make_user(
        email="admin@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_a
    )
    client = _client(admin)
    with django_assert_max_num_queries(14):
        assert client.get(reverse("admin:home")).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("who", "name", "budget"),
    [
        # +4 (backlog AT2): "Attendance to take" (finished lectures, their
        # subjects, enrolments, marks); the same for any number of lectures.
        # +1 (roadmap 5.1): "Answers to grade" is one count.
        ("teacher_1", "teacher:home", 16),
        # +4 (roadmap 4.3): the attendance % (enrolments, marks, lectures,
        # their subjects) and "Lectures today"; the same for any number of
        # children.
        ("student_1", "student:home", 15),
        ("guardian_1", "guardian:home", 14),
    ],
)
def test_portal_home_query_budget(
    busy_school, who, name, budget, django_assert_max_num_queries
) -> None:
    client = _client(getattr(busy_school, who).user)
    with django_assert_max_num_queries(budget):
        assert client.get(reverse(name)).status_code == 200
