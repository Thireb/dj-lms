"""Admin lecture pages: All lectures, Add lecture, Edit (roadmap 3.1)."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from apps.academics.models import TeacherBatchSubject
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.lectures.models import Lecture, LectureStatus
from apps.lectures.views import LectureCreatePage, LectureListPage
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from tests.conftest import cell, make_user, table_row
from tests.lectures.conftest import MEET_URL, add_lecture, put_at, signed_in, soon

KARACHI = ZoneInfo("Asia/Karachi")  # institute A's time zone


def _url(action: str, pk: int | None = None) -> str:
    kwargs = {"pk": pk} if pk is not None else None
    return reverse(f"admin:lecture_{action}", kwargs=kwargs)


def _day() -> datetime:
    return timezone.localtime(soon(days=2), KARACHI)


def _form(school, **fields) -> dict:
    data = {
        "title": "Algebra basics",
        "teacher": school.teacher_1.pk,
        "batch_subjects": [f"{school.morning.pk}:{school.math.pk}"],
        "date": _day().date().isoformat(),
        "start_time": "10:00",
        "duration_minutes": "60",
        "delivery_mode": "manual_link",
        "meeting_url": MEET_URL,
        "description": "",
    }
    data.update(fields)
    return data


def _only_lecture() -> Lecture:
    # unscoped: test assertion outside a tenant context.
    return Lecture.unscoped.get()


# Access


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["list", "create"])
def test_admin_opens_the_pages(admin_client, action) -> None:
    assert admin_client.get(_url(action)).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("page", [LectureListPage, LectureCreatePage])
def test_sub_admin_needs_the_online_lectures_menu(institute_a, page) -> None:
    user = make_user(
        email="sub@example.com", role=Role.SUB_ADMIN, institute=institute_a
    )
    request = RequestFactory().get("/admin/lectures/")
    request.user, request.institute = user, institute_a

    user.allowed_menus = ["online_lectures"]
    with tenant_context(institute_a):
        allowed = page.as_view()(request)
    user.allowed_menus = ["people"]
    denied = page.as_view()(request)

    assert allowed.status_code == 200
    assert denied.status_code == 403


@pytest.mark.django_db
def test_sub_admin_without_menus_gets_403(institute_a) -> None:
    client = signed_in(
        make_user(email="sub@example.com", role=Role.SUB_ADMIN, institute=institute_a)
    )

    assert client.get(_url("list")).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("role", [Role.TEACHER, Role.STUDENT, Role.GUARDIAN])
@pytest.mark.parametrize("action", ["list", "create"])
def test_other_roles_get_403(institute_a, role, action) -> None:
    client = signed_in(
        make_user(email="x@example.com", role=role, institute=institute_a)
    )

    assert client.get(_url(action)).status_code == 403


@pytest.mark.django_db
def test_other_institute_lecture_is_404(school, institute_b) -> None:
    lecture = add_lecture(school)
    client = signed_in(
        make_user(
            email="admin-b@example.com",
            role=Role.INSTITUTE_ADMIN,
            institute=institute_b,
        )
    )

    assert client.get(_url("edit", lecture.pk)).status_code == 404
    assert client.post(_url("edit", lecture.pk), {}).status_code == 404


# List


@pytest.mark.django_db
def test_empty_list_invites_the_first_lecture(admin_client) -> None:
    html = admin_client.get(_url("list")).content.decode()

    assert "No lectures yet." in html
    assert "Add your first lecture" in html


@pytest.mark.django_db
def test_list_shows_lecture_columns_in_the_viewer_zone(admin_client, school) -> None:
    lecture = add_lecture(school, starts_at=soon(days=1, hour=10))
    html = admin_client.get(_url("list")).content.decode()

    row = table_row(html, "Algebra basics")
    local = timezone.localtime(lecture.starts_at, KARACHI)
    assert cell(row, "date") == local.strftime("%a %-d %b %Y").split()
    assert cell(row, "time") == ["3:00", "PM", "to", "4:00", "PM", "PKT"]
    assert cell(row, "batch") == ["Morning"]
    assert cell(row, "subjects") == ["Math"]
    assert cell(row, "mode") == ["Manual", "link"]
    assert cell(row, "status") == ["Scheduled"]
    assert f'href="{_url("edit", lecture.pk)}"' in row
    assert f'href="{MEET_URL}" target="_blank" rel="noopener noreferrer"' in row


@pytest.mark.django_db
def test_other_institute_lectures_never_show(admin_client, school) -> None:
    institute_b = school.batch_b.institute
    with tenant_context(institute_b):
        other = Lecture(
            institute=institute_b,
            title="Institute B lecture",
            teacher=school.teacher_b,
            batch=school.batch_b,
            starts_at=soon(),
            duration_minutes=60,
            meeting_url=MEET_URL,
        )
        other.save()
    add_lecture(school)

    html = admin_client.get(_url("list"), {"show": "all"}).content.decode()

    assert "Algebra basics" in html
    assert "Institute B lecture" not in html


@pytest.mark.django_db
def test_tabs_mark_the_current_list_and_keep_filters(admin_client, school) -> None:
    add_lecture(school)
    html = admin_client.get(
        _url("list"), {"show": "past", "batch": school.morning.pk}
    ).content.decode()

    assert f'href="?batch={school.morning.pk}&amp;show=today"' in html
    assert 'aria-current="page">Past</a>' in html
    assert '<input type="hidden" name="show" value="past" />' in html
    assert "No past lectures." in html


@pytest.mark.django_db
def test_unknown_tab_falls_back_to_upcoming(admin_client, school) -> None:
    add_lecture(school)
    html = admin_client.get(_url("list"), {"show": "x'<b>"}).content.decode()

    assert 'aria-current="page">Upcoming</a>' in html
    assert "Algebra basics" in html


@pytest.mark.django_db
def test_finished_lecture_has_no_edit_action(admin_client, school) -> None:
    lecture = put_at(add_lecture(school), timezone.now() - timedelta(days=1))
    # unscoped: states come with roadmap 3.5; set the state directly.
    Lecture.unscoped.filter(pk=lecture.pk).update(status=LectureStatus.FINISHED)

    html = admin_client.get(_url("list"), {"show": "past"}).content.decode()

    assert cell(table_row(html, "Algebra basics"), "status") == ["Finished"]
    assert _url("edit", lecture.pk) not in html


@pytest.mark.django_db
def test_filter_dropdowns_list_own_institute_only(admin_client, school) -> None:
    html = admin_client.get(_url("list")).content.decode()

    assert f'<option value="{school.teacher_1.pk}">' in html
    assert f'value="{school.teacher_b.pk}"' not in html
    assert f'value="{school.batch_b.pk}"' not in html


# Add


@pytest.mark.django_db
def test_add_form_reloads_subjects_when_the_teacher_changes(
    admin_client, school
) -> None:
    html = admin_client.get(_url("create")).content.decode()

    assert f'hx-get="{_url("create")}"' in html
    assert 'hx-select="#id_batch_subjects"' in html
    assert "Choose a teacher to see their batches." in html


@pytest.mark.django_db
def test_add_form_offers_the_chosen_teacher_pairs_only(admin_client, school) -> None:
    html = admin_client.get(
        _url("create"), {"teacher": school.teacher_2.pk}
    ).content.decode()

    assert f'value="{school.evening.pk}:{school.physics.pk}"' in html
    assert f'value="{school.morning.pk}:{school.math.pk}"' not in html


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["x", "", "99999"])
def test_bad_teacher_param_offers_nothing(admin_client, school, value) -> None:
    html = admin_client.get(_url("create"), {"teacher": value}).content.decode()

    assert "Choose a teacher to see their batches." in html


@pytest.mark.django_db
def test_other_institute_teacher_param_offers_nothing(admin_client, school) -> None:
    html = admin_client.get(
        _url("create"), {"teacher": school.teacher_b.pk}
    ).content.decode()

    assert "Choose a teacher to see their batches." in html


@pytest.mark.django_db
def test_add_saves_in_the_viewer_zone_and_returns_to_list(admin_client, school) -> None:
    response = admin_client.post(_url("create"), _form(school), follow=True)

    lecture = _only_lecture()
    expected = datetime.combine(_day().date(), time(10, 0), tzinfo=KARACHI)
    assert response.redirect_chain[-1][0] == _url("list")
    assert "Lecture added." in response.content.decode()
    assert lecture.starts_at == expected
    assert lecture.teacher == school.teacher_1


@pytest.mark.django_db
def test_subjects_from_two_batches_are_refused(admin_client, school) -> None:
    with tenant_context(school.morning.institute):
        TeacherBatchSubject.objects.create(
            institute=school.morning.institute,
            teacher=school.teacher_1,
            batch=school.evening,
            subject=school.math,
        )
    pairs = [
        f"{school.morning.pk}:{school.math.pk}",
        f"{school.evening.pk}:{school.math.pk}",
    ]

    html = admin_client.post(
        _url("create"), _form(school, batch_subjects=pairs)
    ).content.decode()

    assert "Choose subjects from one batch only." in html
    assert not Lecture.unscoped.exists()


@pytest.mark.django_db
def test_forged_pair_is_refused(admin_client, school) -> None:
    pair = f"{school.evening.pk}:{school.physics.pk}"  # teacher 2's pair
    html = admin_client.post(
        _url("create"), _form(school, batch_subjects=[pair])
    ).content.decode()

    assert "Select a valid choice." in html
    assert not Lecture.unscoped.exists()


@pytest.mark.django_db
def test_online_lecture_without_link_is_refused(admin_client, school) -> None:
    html = admin_client.post(
        _url("create"), _form(school, meeting_url="")
    ).content.decode()

    assert "Paste the meeting link for an online lecture." in html


@pytest.mark.django_db
def test_in_person_lecture_needs_no_link(admin_client, school) -> None:
    admin_client.post(
        _url("create"),
        _form(school, delivery_mode="in_person", meeting_url=MEET_URL),
    )

    assert _only_lecture().meeting_url == ""


@pytest.mark.django_db
def test_teacher_overlap_shows_on_the_start_time(admin_client, school) -> None:
    admin_client.post(_url("create"), _form(school))
    html = admin_client.post(
        _url("create"), _form(school, title="Second", start_time="10:30")
    ).content.decode()

    assert f"{school.teacher_1} already has Algebra basics on " in html
    assert Lecture.unscoped.count() == 1


@pytest.mark.django_db
def test_batch_clash_saves_with_a_warning(admin_client, school) -> None:
    with tenant_context(school.morning.institute):
        TeacherBatchSubject.objects.create(
            institute=school.morning.institute,
            teacher=school.teacher_2,
            batch=school.morning,
            subject=school.physics,
        )
    admin_client.post(_url("create"), _form(school))
    second = _form(
        school,
        title="Physics lab",
        teacher=school.teacher_2.pk,
        batch_subjects=[f"{school.morning.pk}:{school.physics.pk}"],
    )

    html = admin_client.post(_url("create"), second, follow=True).content.decode()

    assert Lecture.unscoped.count() == 2
    assert "toast-warning" in html
    assert "Morning also has Algebra basics on " in html


# Edit


@pytest.mark.django_db
def test_edit_shows_current_values_in_the_viewer_zone(admin_client, school) -> None:
    lecture = add_lecture(school, starts_at=soon(days=1, hour=10))
    html = admin_client.get(_url("edit", lecture.pk)).content.decode()

    local = timezone.localtime(lecture.starts_at, KARACHI)
    assert 'value="Algebra basics"' in html
    assert f'value="{local.date().isoformat()}"' in html
    assert 'value="15:00"' in html
    pair = f"{school.morning.pk}:{school.math.pk}"
    assert f'value="{pair}" id="id_batch_subjects_0_0" checked' in html
    assert f'<option value="{school.teacher_1.pk}" selected>' in html


@pytest.mark.django_db
def test_edit_saves_changes(admin_client, school) -> None:
    lecture = add_lecture(school)

    response = admin_client.post(
        _url("edit", lecture.pk), _form(school, title="Algebra, part 2")
    )

    lecture.refresh_from_db()
    assert response.status_code == 302
    assert lecture.title == "Algebra, part 2"


@pytest.mark.django_db
def test_edit_of_a_finished_lecture_is_refused(admin_client, school) -> None:
    lecture = add_lecture(school)
    # unscoped: states come with roadmap 3.5; set the state directly.
    Lecture.unscoped.filter(pk=lecture.pk).update(status=LectureStatus.FINISHED)

    html = admin_client.post(
        _url("edit", lecture.pk), _form(school, title="Changed")
    ).content.decode()

    lecture.refresh_from_db()
    assert "Only a scheduled lecture can be edited." in html
    assert lecture.title == "Algebra basics"
