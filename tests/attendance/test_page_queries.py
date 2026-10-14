"""Query budgets for the attendance pages. Each page has 8 finished
lectures, so a query per row (N+1) breaks the budget. Raise a budget only
with a reason in the commit."""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from django.urls import reverse

from tests.attendance.conftest import backdate_enrolments, finished, mark
from tests.conftest import make_user
from tests.lectures.conftest import signed_in
from tests.people.conftest import student
from tests.school import link_student


@pytest.fixture
def busy(old_school, institute_a):
    school = old_school
    for number in range(4):
        other = student(institute_a, f"extra-{number}@example.com")
        link_student(other, {school.morning: [school.math]})
    backdate_enrolments()
    for day in range(8):
        lecture = finished(school, title=f"Lecture {day}", days_ago=day + 1)
        if day % 2:
            mark(lecture, {school.student_1: "late"})
    school.first = lecture
    school.admin = make_user(
        email="admin@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_a
    )
    return school


PAGES = [
    # Same count with 16 lectures as with 8 (checked by hand at build time).
    ("student_1", lambda s: reverse("student:attendance"), 12),
    ("guardian_1", lambda s: reverse("guardian:attendance"), 10),
    (
        "admin",
        lambda s: (
            reverse("admin:student_attendance_history") + f"?student={s.student_1.pk}"
        ),
        10,
    ),
    (
        "teacher_1",
        lambda s: reverse("teacher:lecture_attendance", kwargs={"pk": s.first.pk}),
        9,
    ),
]


@pytest.mark.django_db
@pytest.mark.parametrize(("who", "url", "budget"), PAGES)
def test_attendance_page_query_budget(
    busy, who, url, budget, django_assert_max_num_queries
) -> None:
    person = getattr(busy, who)
    client = signed_in(getattr(person, "user", person))
    page = url(busy)
    with django_assert_max_num_queries(budget):
        assert client.get(page).status_code == 200
