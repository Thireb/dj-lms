"""Query budgets for the dashboards (redesign audit RA8).

Each page is loaded with more people than it lists, so a query per row
(N+1) breaks the budget. Raise a budget only with a reason in the commit.
"""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from django.test import Client
from django.urls import reverse

from tests.conftest import make_user
from tests.people.conftest import student
from tests.school import link_guardian, link_student


@pytest.fixture
def busy_school(school, institute_a):
    for number in range(8):
        extra = student(institute_a, f"extra{number}@example.com")
        link_student(extra, {school.morning: [school.math, school.physics]})
    link_guardian(student(institute_a, "sibling@example.com"), "g1-a@example.com")
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
    with django_assert_max_num_queries(13):
        assert client.get(reverse("admin:home")).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("who", "name", "budget"),
    [
        ("teacher_1", "teacher:home", 7),
        ("student_1", "student:home", 7),
        ("guardian_1", "guardian:home", 8),
    ],
)
def test_portal_home_query_budget(
    busy_school, who, name, budget, django_assert_max_num_queries
) -> None:
    client = _client(getattr(busy_school, who).user)
    with django_assert_max_num_queries(budget):
        assert client.get(reverse(name)).status_code == 200
