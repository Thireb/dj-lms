"""Query budgets for the lecture pages (Phase 3 audit P3-5).

The pages are loaded with a dozen lectures, so a query per row (N+1) breaks
the budget. Raise a budget only with a reason in the commit.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from apps.core.roles import Role
from apps.lectures.models import Lecture, LectureStatus
from django.urls import reverse
from django.utils import timezone

from tests.conftest import make_user
from tests.lectures.conftest import add_lecture, add_schedule, put_at, signed_in, soon
from tests.school import link_guardian


@pytest.fixture
def busy(school, institute_a):
    for day in range(12):
        lecture = add_lecture(
            school, title=f"Lecture {day}", starts_at=soon(days=day + 1)
        )
        if day % 3 == 0:
            # unscoped: test set-up; finished lectures for the history pages.
            Lecture.unscoped.filter(pk=lecture.pk).update(status=LectureStatus.FINISHED)
            put_at(lecture, timezone.now() - timedelta(days=day + 1))
    start = timezone.now().date() + timedelta(days=40)
    add_schedule(school, title="Later", start_date=start, end_date=start + timedelta(6))
    link_guardian(school.student_2, "g1-a@example.com")
    school.admin = make_user(
        email="admin@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_a
    )
    return school


def _detail(school) -> str:
    lecture = Lecture.unscoped.filter(teacher=school.teacher_1).first()
    return reverse("admin:lecture_detail", kwargs={"pk": lecture.pk})


PAGES = [
    ("admin", lambda s: reverse("admin:lecture_list") + "?show=all", 11),
    ("admin", _detail, 7),
    ("admin", lambda s: reverse("admin:lecture_schedule_list"), 9),
    ("admin", lambda s: reverse("admin:teacher_lecture_history"), 9),
    ("admin", lambda s: reverse("admin:dashboard_lectures"), 8),
    ("teacher_1", lambda s: reverse("teacher:lecture_list") + "?show=all", 10),
    ("teacher_1", lambda s: reverse("teacher:schedule") + "?view=month", 6),
    ("teacher_1", lambda s: reverse("teacher:lecture_history"), 8),
    ("student_1", lambda s: reverse("student:lecture_list") + "?show=all", 10),
    ("guardian_1", lambda s: reverse("guardian:lecture_schedule") + "?show=all", 9),
]


@pytest.mark.django_db
@pytest.mark.parametrize(("who", "url", "budget"), PAGES)
def test_lecture_page_query_budget(
    busy, who, url, budget, django_assert_max_num_queries
) -> None:
    person = getattr(busy, who)
    client = signed_in(getattr(person, "user", person))
    page = url(busy)
    with django_assert_max_num_queries(budget):
        assert client.get(page).status_code == 200
