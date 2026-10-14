"""Recurring schedule pages, admin and teacher (roadmap 3.2, SPEC 3 and 4.6)."""

from __future__ import annotations

import re
from datetime import time, timedelta

import pytest
from apps.core.roles import Role
from apps.lectures.models import Lecture, LectureStatus, RecurringSchedule
from django.urls import reverse

from tests.conftest import cell, make_user, table_row
from tests.lectures.conftest import (
    MEET_URL,
    add_schedule,
    karachi_today,
    schedule_lectures,
    signed_in,
)


def _url(action: str, pk: int | None = None, portal: str = "admin") -> str:
    kwargs = {"pk": pk} if pk is not None else None
    return reverse(f"{portal}:lecture_schedule_{action}", kwargs=kwargs)


def _form(school, **fields) -> dict:
    start = karachi_today() + timedelta(days=1)
    data = {
        "title": "Daily algebra",
        "teacher": school.teacher_1.pk,
        "batch_subjects": [f"{school.morning.pk}:{school.math.pk}"],
        "weekdays": ["0", "1", "2", "3", "4", "5", "6"],
        "start_time": "10:00",
        "duration_minutes": "60",
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=6)).isoformat(),
        "weeks": "",
        "delivery_mode": "manual_link",
        "meeting_url": MEET_URL,
        "description": "",
    }
    data.update(fields)
    return data


def _token(html: str) -> str:
    match = re.search(r'name="confirm" value="([0-9a-f]+)"', html)
    assert match, "no confirm token"
    return match.group(1)


def _preview_then_save(client, url: str, data: dict, *, capture):
    preview = client.post(url, data).content.decode()
    with capture(execute=True):
        return client.post(url, {**data, "confirm": _token(preview)}, follow=True)


# Access


@pytest.mark.django_db
@pytest.mark.parametrize("role", [Role.TEACHER, Role.STUDENT, Role.GUARDIAN])
@pytest.mark.parametrize("action", ["list", "create"])
def test_other_roles_get_403_on_admin_pages(institute_a, role, action) -> None:
    client = signed_in(
        make_user(email="x@example.com", role=role, institute=institute_a)
    )

    assert client.get(_url(action)).status_code == 403


@pytest.mark.django_db
def test_other_institute_schedule_is_404(school, institute_b) -> None:
    schedule = add_schedule(school)
    client = signed_in(
        make_user(
            email="b@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_b
        )
    )

    for action in ("edit", "extend"):
        assert client.get(_url(action, schedule.pk)).status_code == 404
    assert client.post(_url("stop", schedule.pk)).status_code == 404


@pytest.mark.django_db
def test_teacher_cannot_open_another_teacher_schedule(school) -> None:
    schedule = add_schedule(school)
    client = signed_in(school.teacher_2.user)

    for action in ("edit", "extend"):
        assert client.get(_url(action, schedule.pk, "teacher")).status_code == 404
    assert client.post(_url("stop", schedule.pk, "teacher")).status_code == 404


# List


@pytest.mark.django_db
def test_empty_list_invites_the_first_schedule(admin_client) -> None:
    html = admin_client.get(_url("list")).content.decode()

    assert "No recurring schedules yet." in html
    assert "Add your first schedule" in html


@pytest.mark.django_db
def test_list_shows_schedule_columns(admin_client, school) -> None:
    schedule = add_schedule(school, weekdays=[4, 0, 2])
    html = admin_client.get(_url("list")).content.decode()

    row = table_row(html, "Daily algebra")
    assert cell(row, "days") == ["Mon,", "Wed,", "Fri"]
    assert cell(row, "time") == ["10:00", "AM", "PKT"]
    assert cell(row, "lectures") == [str(len(schedule_lectures(schedule)))]
    assert cell(row, "status") == ["Active"]
    assert _url("edit", schedule.pk) in row
    assert _url("extend", schedule.pk) in row
    assert _url("stop", schedule.pk) in row


@pytest.mark.django_db
def test_stopped_schedule_has_no_actions(admin_client, school) -> None:
    schedule = add_schedule(school)
    admin_client.post(_url("stop", schedule.pk))

    row = table_row(admin_client.get(_url("list")).content.decode(), "Daily algebra")

    assert cell(row, "status") == ["Stopped"]
    assert _url("edit", schedule.pk) not in row


# Create with preview


@pytest.mark.django_db
def test_first_submit_shows_a_preview_and_saves_nothing(admin_client, school) -> None:
    html = admin_client.post(_url("create"), _form(school)).content.decode()

    assert "7 lectures will be added now" in html
    assert html.count(">New<") == 7
    assert re.search(r'type="submit"[^>]*>\s*Create schedule\s*<', html)
    assert not RecurringSchedule.unscoped.exists()


@pytest.mark.django_db
def test_second_submit_saves_and_makes_the_lectures(
    admin_client, school, django_capture_on_commit_callbacks
) -> None:
    response = _preview_then_save(
        admin_client,
        _url("create"),
        _form(school),
        capture=django_capture_on_commit_callbacks,
    )

    schedule = RecurringSchedule.unscoped.get()
    assert response.redirect_chain[-1][0] == _url("list")
    assert "Schedule saved. Its lectures are being added." in response.content.decode()
    assert schedule.time_zone == "Asia/Karachi"  # the admin's zone
    assert len(schedule_lectures(schedule)) == 7


@pytest.mark.django_db
def test_a_changed_value_after_the_preview_shows_a_new_preview(
    admin_client, school
) -> None:
    preview = admin_client.post(_url("create"), _form(school)).content.decode()
    changed = _form(school, start_time="11:00", confirm=_token(preview))

    html = admin_client.post(_url("create"), changed).content.decode()

    assert "lectures will be added now" in html
    assert not RecurringSchedule.unscoped.exists()


@pytest.mark.django_db
def test_weeks_instead_of_an_end_date(admin_client, school) -> None:
    html = admin_client.post(
        _url("create"), _form(school, end_date="", weeks="1")
    ).content.decode()

    assert "7 lectures will be added now" in html


@pytest.mark.django_db
def test_end_date_or_weeks_is_needed(admin_client, school) -> None:
    html = admin_client.post(
        _url("create"), _form(school, end_date="", weeks="")
    ).content.decode()

    assert "Enter an end date or a number of weeks." in html


@pytest.mark.django_db
def test_service_errors_show_on_the_form(admin_client, school) -> None:
    yesterday = (karachi_today() - timedelta(days=1)).isoformat()
    html = admin_client.post(
        _url("create"), _form(school, start_date=yesterday)
    ).content.decode()

    assert "Choose a start date from today on." in html


# Edit, extend, stop


@pytest.mark.django_db
def test_edit_shows_current_values_and_saves(
    admin_client, school, django_capture_on_commit_callbacks
) -> None:
    schedule = add_schedule(school)
    page = admin_client.get(_url("edit", schedule.pk)).content.decode()

    response = _preview_then_save(
        admin_client,
        _url("edit", schedule.pk),
        _form(school, start_time="15:00"),
        capture=django_capture_on_commit_callbacks,
    )

    assert 'value="10:00"' in page
    assert re.search(r'type="submit"[^>]*>\s*Preview lectures\s*<', page)
    assert "7 upcoming lectures are being remade." in response.content.decode()
    hours = {lec.starts_at.hour for lec in schedule_lectures(schedule)}
    assert hours == {10}  # 15:00 in Karachi is 10:00 UTC


@pytest.mark.django_db
def test_extend_page(admin_client, school, django_capture_on_commit_callbacks) -> None:
    schedule = add_schedule(school)
    later = (schedule.end_date + timedelta(days=2)).isoformat()

    page = admin_client.get(_url("extend", schedule.pk)).content.decode()
    with django_capture_on_commit_callbacks(execute=True):
        admin_client.post(_url("extend", schedule.pk), {"end_date": later})
    early = admin_client.post(
        _url("extend", schedule.pk), {"end_date": schedule.end_date.isoformat()}
    ).content.decode()

    assert "Daily algebra ends on" in page
    assert len(schedule_lectures(schedule)) == 9
    assert "Choose a date after the current end date." in early


@pytest.mark.django_db
def test_stop_cancels_upcoming_lectures(admin_client, school) -> None:
    schedule = add_schedule(school)

    response = admin_client.post(_url("stop", schedule.pk), follow=True)

    assert "Daily algebra stopped. 7 lectures cancelled." in response.content.decode()
    assert not Lecture.unscoped.filter(
        schedule=schedule, status=LectureStatus.SCHEDULED
    ).exists()


@pytest.mark.django_db
def test_stop_needs_post(admin_client, school) -> None:
    schedule = add_schedule(school)

    assert admin_client.get(_url("stop", schedule.pk)).status_code == 405


@pytest.mark.django_db
def test_lecture_edit_page_says_it_belongs_to_a_schedule(admin_client, school) -> None:
    lecture = schedule_lectures(add_schedule(school))[0]

    html = admin_client.get(
        reverse("admin:lecture_edit", kwargs={"pk": lecture.pk})
    ).content.decode()

    assert "Part of the schedule Daily algebra." in html


# Teacher


@pytest.mark.django_db
def test_teacher_creates_a_schedule_for_themselves(
    school, django_capture_on_commit_callbacks
) -> None:
    client = signed_in(school.teacher_1.user)
    form = _form(school, teacher=school.teacher_2.pk)

    _preview_then_save(
        client,
        _url("create", portal="teacher"),
        form,
        capture=django_capture_on_commit_callbacks,
    )

    assert RecurringSchedule.unscoped.get().teacher == school.teacher_1


@pytest.mark.django_db
def test_teacher_list_shows_own_schedules_and_the_menu_item(school) -> None:
    add_schedule(school)
    add_schedule(
        school,
        title="Evening physics",
        teacher=school.teacher_2,
        batch=school.evening,
        subjects=[school.physics],
    )

    html = signed_in(school.teacher_1.user).get(_url("list", portal="teacher"))
    html = html.content.decode()

    assert "Daily algebra" in html
    assert "Evening physics" not in html
    assert "cell-teacher" not in html
    assert re.search(
        rf'href="{_url("list", portal="teacher")}"[^>]*aria-current="page"', html
    )


@pytest.mark.django_db
def test_edit_keeps_the_schedule_time_zone(
    admin_client, school, django_capture_on_commit_callbacks
) -> None:
    schedule = add_schedule(school, time_zone="Europe/London")

    page = admin_client.get(_url("edit", schedule.pk)).content.decode()
    _preview_then_save(
        admin_client,
        _url("edit", schedule.pk),
        _form(school, title="Renamed"),
        capture=django_capture_on_commit_callbacks,
    )

    schedule.refresh_from_db()
    assert "Times are in Europe/London." in page
    assert schedule.time_zone == "Europe/London"


@pytest.mark.django_db
def test_preview_marks_a_busy_date_as_skipped(admin_client, school) -> None:
    add_schedule(school, title="Existing")

    html = admin_client.post(_url("create"), _form(school)).content.decode()

    assert "0 lectures will be added now" in html
    assert html.count(">Skipped<") == 7
    assert "The teacher already has Existing then." in html


# External audit (Phase 3)


@pytest.mark.django_db
def test_preview_is_one_line_per_date_with_save_on_top(admin_client, school) -> None:
    """L3: no table cards with an empty Note row; Save above the dates."""
    add_schedule(school, title="Existing", weekdays=[0])

    html = admin_client.post(_url("create"), _form(school)).content.decode()

    card = html.split("lectures will be added now", 1)[1]
    save = re.search(r'<button type="submit" class="btn btn-primary">', card)
    first_row = card.index("lecture-row")
    assert save and save.start() < first_row
    assert html.count('class="lecture-row') == 7
    assert 'data-label="Note"' not in html
    assert html.count("The teacher already has Existing then.") == 1


@pytest.mark.django_db
def test_list_flags_a_schedule_that_makes_no_lectures(admin_client, school) -> None:
    """L5: the generator skipped it silently; the list now says why."""
    from apps.academics.models import TeacherBatchSubject

    broken = add_schedule(school)
    add_schedule(
        school,
        title="Evening physics",
        teacher=school.teacher_2,
        batch=school.evening,
        subjects=[school.physics],
    )
    # unscoped: test set-up; the teacher stops teaching Math in Morning.
    TeacherBatchSubject.unscoped.filter(
        teacher=school.teacher_1, subject=school.math
    ).delete()

    html = admin_client.get(_url("list")).content.decode()

    row = table_row(html, "Daily algebra")
    assert cell(row, "status")[:2] == ["Needs", "attention"]
    assert f"{school.teacher_1} no longer teaches Math in Morning" in row
    assert cell(table_row(html, "Evening physics"), "status") == ["Active"]
    assert broken.status == "active"


@pytest.mark.django_db
def test_list_flags_an_inactive_teacher_but_not_a_stopped_schedule(
    admin_client, school
) -> None:
    from apps.people.models import ProfileStatus, TeacherProfile

    add_schedule(school)
    stopped = add_schedule(school, title="Old algebra", start_time=time(18, 0))
    admin_client.post(_url("stop", stopped.pk))
    # unscoped: test set-up outside a tenant context.
    TeacherProfile.unscoped.filter(pk=school.teacher_1.pk).update(
        status=ProfileStatus.INACTIVE
    )

    html = admin_client.get(_url("list")).content.decode()

    assert "is inactive, so no new lectures are made." in table_row(
        html, "Daily algebra"
    )
    assert cell(table_row(html, "Old algebra"), "status") == ["Stopped"]


# Phase 4 re-audit


@pytest.mark.django_db
def test_preview_lists_the_first_ten_dates(admin_client, school) -> None:
    """P4-6: 21 dates were 3799px tall at 360px. The list shows 10 and
    says how many more; the card title keeps the full count."""
    start = karachi_today() + timedelta(days=1)
    data = _form(school, end_date=(start + timedelta(days=20)).isoformat())

    html = admin_client.post(_url("create"), data).content.decode()

    assert "21 lectures will be added now" in html
    assert html.count('class="lecture-row') == 10
    assert "and 11 more dates." in html


@pytest.mark.django_db
def test_preview_says_how_many_hidden_dates_are_skipped(admin_client, school) -> None:
    start = karachi_today() + timedelta(days=1)
    last = start + timedelta(days=13)
    add_schedule(
        school,
        title="Existing",
        weekdays=[0, 1, 2, 3, 4, 5, 6],
        start_date=start + timedelta(days=12),
        end_date=last,
    )

    html = admin_client.post(
        _url("create"), _form(school, end_date=last.isoformat())
    ).content.decode()

    assert "12 lectures will be added now" in html
    assert "and 4 more dates, 2 of them skipped." in html


@pytest.mark.django_db
def test_preview_of_ten_dates_has_no_more_line(admin_client, school) -> None:
    start = karachi_today() + timedelta(days=1)
    data = _form(school, end_date=(start + timedelta(days=9)).isoformat())
    html = admin_client.post(_url("create"), data).content.decode()
    assert html.count('class="lecture-row') == 10
    assert "more date" not in html
