"""Teacher "Attendance to take" (backlog AT2): finished lectures with no
marks and at least one expected student."""

from __future__ import annotations

import pytest
from apps.attendance.services import lectures_to_mark
from apps.core.tenancy import tenant_context
from apps.lectures.models import LectureStatus
from django.urls import reverse

from tests.attendance.conftest import finished, mark
from tests.lectures.conftest import add_lecture, signed_in, soon


def _titles(school, user) -> set[str]:
    with tenant_context(school.morning.institute):
        return {lecture.title for lecture in lectures_to_mark(user)}


@pytest.mark.django_db
def test_only_finished_unmarked_lectures_with_students(old_school) -> None:
    school = old_school
    finished(school, title="To mark")
    mark(finished(school, title="Marked", days_ago=2), {school.student_1: "absent"})
    # Enrolments are 60 days old, so nobody was expected 90 days ago.
    finished(school, title="Nobody", days_ago=90)
    add_lecture(school, title="Later", starts_at=soon(days=1))
    finished(
        school,
        title="Other teacher",
        teacher=school.teacher_2,
        batch=school.evening,
        subjects=[school.physics],
    )

    assert _titles(school, school.teacher_1.user) == {"To mark"}
    assert _titles(school, school.teacher_2.user) == {"Other teacher"}


@pytest.mark.django_db
def test_not_held_lecture_is_not_counted(old_school) -> None:
    school = old_school
    lecture = finished(school, title="Never ran")
    lecture.status = LectureStatus.NOT_HELD
    lecture.save(update_fields=["status"])
    assert _titles(school, school.teacher_1.user) == set()


@pytest.mark.django_db
def test_teacher_home_shows_the_count(old_school) -> None:
    school = old_school
    finished(school, title="One")
    finished(school, title="Two", days_ago=2)
    html = signed_in(school.teacher_1.user).get(reverse("teacher:home"))
    text = html.content.decode()
    card = text.split("Attendance to take")[0][-80:]
    assert ">2</p>" in card
    assert "Finished lectures with no marks" in text
