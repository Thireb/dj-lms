"""Roadmap 4.1 pages: Take attendance, the lecture page card, the row action
and Lecture history Present / Total."""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from apps.lectures.models import Lecture, LectureStatus
from django.urls import reverse

from tests.attendance.conftest import finished, mark, marks_of
from tests.conftest import cell, make_user, table_row
from tests.lectures.conftest import add_lecture, signed_in


def _url(lecture) -> str:
    return reverse("teacher:lecture_attendance", kwargs={"pk": lecture.pk})


def _detail(portal: str, lecture) -> str:
    return reverse(f"{portal}:lecture_detail", kwargs={"pk": lecture.pk})


def _field(school) -> str:
    return f"student_{school.student_1.pk}"


# Access


@pytest.mark.django_db
def test_other_roles_get_403(old_school, institute_a) -> None:
    url = _url(finished(old_school))
    for role in (Role.INSTITUTE_ADMIN, Role.SUB_ADMIN, Role.STUDENT, Role.GUARDIAN):
        user = make_user(email=f"{role}@example.com", role=role, institute=institute_a)
        assert signed_in(user).get(url).status_code == 403, role


@pytest.mark.django_db
def test_other_teacher_gets_404(old_school) -> None:
    url = _url(finished(old_school))
    assert signed_in(old_school.teacher_2.user).get(url).status_code == 404
    assert signed_in(old_school.teacher_b.user).get(url).status_code == 404


@pytest.mark.django_db
def test_other_teacher_cannot_post_marks(old_school) -> None:
    school = old_school
    lecture = finished(school)
    response = signed_in(school.teacher_2.user).post(
        _url(lecture), {_field(school): "absent"}
    )
    assert response.status_code == 404
    assert marks_of(lecture) == {}


# The form


@pytest.mark.django_db
def test_form_lists_the_roster_with_present_first(old_school) -> None:
    school = old_school
    html = signed_in(school.teacher_1.user).get(_url(finished(school))).content
    html = html.decode()
    name = _field(school)
    assert f'name="{name}" value="present" id="id_{name}_0" checked' in html
    assert f'name="{name}" value="absent"' in html
    assert 'role="radiogroup" aria-label="Attendance for' in html
    assert f"student_{school.student_2.pk}" not in html  # another batch
    assert "Save attendance" in html


@pytest.mark.django_db
def test_form_shows_the_saved_mark(old_school) -> None:
    school = old_school
    lecture = finished(school)
    mark(lecture, {school.student_1: "late"})
    html = signed_in(school.teacher_1.user).get(_url(lecture)).content.decode()
    name = _field(school)
    assert f'value="late" id="id_{name}_2" checked' in html
    assert f'value="present" id="id_{name}_0" checked' not in html


@pytest.mark.django_db
def test_post_saves_and_goes_to_the_lecture(old_school) -> None:
    school = old_school
    lecture = finished(school)
    response = signed_in(school.teacher_1.user).post(
        _url(lecture), {_field(school): "absent"}
    )
    assert response.status_code == 302
    assert response["Location"] == _detail("teacher", lecture)
    assert marks_of(lecture) == {school.student_1.pk: "absent"}


@pytest.mark.django_db
def test_post_with_a_bad_status_shows_the_error(old_school) -> None:
    school = old_school
    lecture = finished(school)
    response = signed_in(school.teacher_1.user).post(
        _url(lecture), {_field(school): "excused"}
    )
    assert response.status_code == 200
    assert "Select a valid choice" in response.content.decode()
    assert marks_of(lecture) == {}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status",
    [LectureStatus.SCHEDULED, LectureStatus.LIVE, LectureStatus.NOT_HELD],
)
def test_open_or_not_held_lecture_goes_back_to_its_page(old_school, status) -> None:
    school = old_school
    lecture = finished(school)
    # unscoped: test set-up outside a tenant context.
    Lecture.unscoped.filter(pk=lecture.pk).update(status=status)
    client = signed_in(school.teacher_1.user)
    for response in (
        client.get(_url(lecture)),
        client.post(_url(lecture), {_field(school): "absent"}),
    ):
        assert response.status_code == 302
        assert response["Location"] == _detail("teacher", lecture)
    assert marks_of(lecture) == {}


@pytest.mark.django_db
def test_no_students_shows_an_empty_state(school) -> None:
    """The fixture's enrolments are newer than the lecture."""
    html = signed_in(school.teacher_1.user).get(_url(finished(school, days_ago=3)))
    html = html.content.decode()
    assert "No students to mark." in html
    assert "Save attendance" not in html


# The lecture page


@pytest.mark.django_db
def test_teacher_page_has_take_then_edit_attendance(old_school) -> None:
    school = old_school
    lecture = finished(school)
    client = signed_in(school.teacher_1.user)
    html = client.get(_detail("teacher", lecture)).content.decode()
    assert "Take attendance" in html
    assert _url(lecture) in html
    assert "Not marked" in html
    mark(lecture, {school.student_1: "partial"})
    html = client.get(_detail("teacher", lecture)).content.decode()
    assert "Edit attendance" in html
    assert ">Partial<" in html


@pytest.mark.django_db
def test_admin_page_shows_marks_read_only(old_school, admin_client) -> None:
    school = old_school
    lecture = finished(school)
    mark(lecture, {school.student_1: "absent"})
    html = admin_client.get(_detail("admin", lecture)).content.decode()
    row = table_row(html, str(school.student_1))
    assert cell(row, "status") == ["Absent"]
    assert "Take attendance" not in html
    assert "Edit attendance" not in html


@pytest.mark.django_db
def test_scheduled_lecture_page_has_no_attendance(old_school) -> None:
    lecture = add_lecture(old_school)
    html = signed_in(old_school.teacher_1.user).get(_detail("teacher", lecture))
    html = html.content.decode()
    assert "Take attendance" not in html
    assert ">Attendance<" not in html


@pytest.mark.django_db
def test_teacher_list_row_has_attendance_for_finished_only(old_school) -> None:
    school = old_school
    done = finished(school, title="Done lecture")
    coming = add_lecture(school, title="Coming lecture")
    html = signed_in(school.teacher_1.user).get(
        reverse("teacher:lecture_list"), {"show": "all"}
    )
    html = html.content.decode()
    assert _url(done) in table_row(html, "Done lecture")
    assert _url(coming) not in html
    assert 'aria-label="Attendance for Done lecture"' in html


# Lecture history


@pytest.mark.django_db
@pytest.mark.parametrize("portal", ["teacher", "admin"])
def test_history_shows_present_total(old_school, admin_client, portal) -> None:
    school = old_school
    taken = finished(school, title="Taken lecture")
    finished(school, title="Untaken lecture", days_ago=2)
    mark(taken, {school.student_1: "late"})
    if portal == "teacher":
        client = signed_in(school.teacher_1.user)
        url = reverse("teacher:lecture_history")
    else:
        client = admin_client
        url = reverse("admin:teacher_lecture_history")
    html = client.get(url).content.decode()
    assert cell(table_row(html, "Taken lecture"), "attendance") == ["1", "/", "1"]
    assert cell(table_row(html, "Untaken lecture"), "attendance") == [
        "Not",
        "taken",
    ]
