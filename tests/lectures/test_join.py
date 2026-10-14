"""Join states, the Join button and view, "Up next" and lectures today
(roadmap 3.4, SPEC 6.4 and 8)."""

from __future__ import annotations

import re
from datetime import UTC, timedelta

import pytest
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.institutes.models import InstituteSettings
from apps.lectures.models import DeliveryMode, Lecture, LectureStatus
from apps.lectures.services import (
    JOIN_ENDED,
    JOIN_NONE,
    JOIN_OPEN,
    JOIN_SOON,
    JOIN_WAITING,
    join_state,
    join_window_minutes,
    lectures_today_count,
    next_lecture,
)
from django.urls import reverse
from django.utils import timezone

from tests.conftest import cell, make_user, table_row
from tests.lectures.conftest import MEET_URL, add_lecture, put_at, signed_in, soon
from tests.school import link_guardian

LIST_URL = reverse("student:lecture_list")


def _set_status(lecture: Lecture, status: str) -> Lecture:
    # unscoped: states come with roadmap 3.5; set the state directly.
    Lecture.unscoped.filter(pk=lecture.pk).update(status=status)
    lecture.refresh_from_db()
    return lecture


def _starting_in(school, minutes: int, **fields) -> Lecture:
    lecture = add_lecture(school, **fields)
    return put_at(lecture, timezone.now() + timedelta(minutes=minutes))


def _join_url(lecture: Lecture) -> str:
    return reverse("student:lecture_join", kwargs={"pk": lecture.pk})


# States


@pytest.mark.django_db
def test_join_states_follow_the_window_and_the_teacher(school) -> None:
    lecture = add_lecture(school)
    start = lecture.starts_at
    window = 10

    def state(at, status=LectureStatus.SCHEDULED):
        lecture.status = status
        return join_state(lecture, now=at, window=window)

    assert state(start - timedelta(minutes=11)) == JOIN_SOON
    assert state(start - timedelta(minutes=10)) == JOIN_WAITING  # window opens
    assert state(start + timedelta(minutes=5)) == JOIN_WAITING
    assert state(start - timedelta(minutes=30), LectureStatus.LIVE) == JOIN_OPEN
    assert state(start + timedelta(minutes=59), LectureStatus.LIVE) == JOIN_OPEN
    assert state(start + timedelta(minutes=60), LectureStatus.LIVE) == JOIN_ENDED
    assert state(start, LectureStatus.FINISHED) == JOIN_ENDED
    assert state(start, LectureStatus.CANCELLED) == JOIN_NONE


@pytest.mark.django_db
def test_in_person_lecture_has_nothing_to_join(school) -> None:
    lecture = add_lecture(school, delivery_mode=DeliveryMode.IN_PERSON, meeting_url="")

    assert join_state(lecture, now=lecture.starts_at, window=10) == JOIN_NONE


@pytest.mark.django_db
def test_join_window_comes_from_the_settings(institute_a) -> None:
    with tenant_context(institute_a):
        assert join_window_minutes(institute_a) == 10
    # unscoped: test set-up outside a tenant context.
    InstituteSettings.unscoped.update_or_create(
        institute=institute_a, defaults={"join_window_minutes": 0}
    )

    with tenant_context(institute_a):
        assert join_window_minutes(institute_a) == 0


# Next lecture and lectures today


@pytest.mark.django_db
def test_next_lecture_is_the_running_one_then_the_next(school) -> None:
    running = put_at(add_lecture(school, title="Running"), timezone.now())
    later = add_lecture(school, title="Later", starts_at=soon(days=2))
    ended = add_lecture(school, title="Ended", starts_at=soon(days=3))
    put_at(ended, timezone.now() - timedelta(days=1))
    user = school.teacher_1.user

    assert next_lecture(user) == running
    _set_status(running, LectureStatus.CANCELLED)
    assert next_lecture(user) == later
    assert next_lecture(school.teacher_2.user) is None
    assert next_lecture(school.student_1.user) == later
    assert next_lecture(school.student_2.user) is None


@pytest.mark.django_db
def test_next_lecture_skips_finished_ones(school) -> None:
    finished = put_at(add_lecture(school), timezone.now())
    _set_status(finished, LectureStatus.FINISHED)

    assert next_lecture(school.teacher_1.user) is None


@pytest.mark.django_db
def test_lectures_today_leaves_out_cancelled_and_other_days(school) -> None:
    now = timezone.now()
    with timezone.override("UTC"):
        noon = now.replace(hour=12, minute=0, second=0, microsecond=0)
        put_at(add_lecture(school, title="Today"), noon)
        dropped = put_at(add_lecture(school, title="Dropped"), noon)
        _set_status(dropped, LectureStatus.CANCELLED)
        put_at(add_lecture(school, title="Tomorrow"), noon + timedelta(days=1))

        assert lectures_today_count(school.teacher_1.user, now=noon) == 1
        assert lectures_today_count(school.teacher_2.user, now=noon) == 0


# Join view


@pytest.mark.django_db
def test_join_sends_the_student_to_the_link_once_the_teacher_starts(school) -> None:
    lecture = _set_status(_starting_in(school, 5), LectureStatus.LIVE)

    response = signed_in(school.student_1.user).post(_join_url(lecture))

    assert response.status_code == 302
    assert response["Location"] == MEET_URL


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("minutes", "message"),
    [
        (30, "Join opens at "),
        (5, "The teacher has not started this lecture yet."),
        (-120, "This lecture has ended."),
    ],
)
def test_join_is_refused_before_the_teacher_starts(school, minutes, message) -> None:
    lecture = _starting_in(school, minutes)
    client = signed_in(school.student_1.user)

    response = client.post(_join_url(lecture), follow=True)

    assert response.redirect_chain[-1][0] == LIST_URL
    assert message in response.content.decode()
    assert MEET_URL not in response.redirect_chain[-1][0]


@pytest.mark.django_db
def test_join_needs_post_and_an_enrolled_student(school) -> None:
    lecture = _set_status(_starting_in(school, 5), LectureStatus.LIVE)

    assert signed_in(school.student_1.user).get(_join_url(lecture)).status_code == 405
    assert signed_in(school.student_2.user).post(_join_url(lecture)).status_code == 404
    assert signed_in(school.student_b.user).post(_join_url(lecture)).status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role", [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN, Role.TEACHER, Role.GUARDIAN]
)
def test_join_is_for_students_only(school, institute_a, role) -> None:
    lecture = _set_status(_starting_in(school, 5), LectureStatus.LIVE)
    client = signed_in(
        make_user(email="x@example.com", role=role, institute=institute_a)
    )

    assert client.post(_join_url(lecture)).status_code == 403


# Join column


def _student_list(school) -> str:
    return signed_in(school.student_1.user).get(LIST_URL).content.decode()


@pytest.mark.django_db
def test_join_column_shows_each_state(school) -> None:
    _starting_in(school, 60, title="Later today")
    _starting_in(school, 5, title="About to start")
    live = _set_status(_starting_in(school, 2, title="Started"), LectureStatus.LIVE)
    _starting_in(
        school,
        90,
        title="Room class",
        delivery_mode=DeliveryMode.IN_PERSON,
        meeting_url="",
    )

    html = _student_list(school)

    later = table_row(html, "Later today")
    assert re.search(r"<button[^>]*disabled[^>]*>\s*Join opens soon", later)
    assert 'title="Join opens at ' in later
    assert cell(table_row(html, "About to start"), "join") == ["Waiting", "for", "host"]
    started = table_row(html, "Started")
    assert f'action="{_join_url(live)}"' in started
    assert 'name="csrfmiddlewaretoken"' in started
    assert cell(table_row(html, "Room class"), "join") == ["In", "person"]
    assert MEET_URL not in html  # the link shows only through the join view


@pytest.mark.django_db
def test_guardian_list_has_no_join_column(school) -> None:
    _starting_in(school, 5)

    html = signed_in(school.guardian_1.user).get(reverse("guardian:lecture_schedule"))

    assert "cell-join" not in html.content.decode()


# Homes and the up-next card


def _home(user, name: str) -> str:
    response = signed_in(user).get(reverse(name))
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
def test_student_home_counts_down_to_the_next_lecture(school) -> None:
    lecture = _starting_in(school, 5, title="Algebra basics")

    html = _home(school.student_1.user, "student:home")

    card = html.split("countdown-card", 1)[1]
    iso = lecture.starts_at.astimezone(UTC).isoformat()
    assert "Algebra basics" in card
    assert f'data-scheduled-at="{iso}"' in html
    assert "Waiting for host" in card
    assert str(school.teacher_1) in card
    assert f'hx-get="{reverse("student:up_next")}"' in html


@pytest.mark.django_db
def test_teacher_home_has_the_meeting_link_and_lectures_today(school) -> None:
    # Starts now, so it is today at any time of day.
    _starting_in(school, 0, title="Algebra basics")

    html = _home(school.teacher_1.user, "teacher:home")

    card = html.split("countdown-card", 1)[1]
    assert "Algebra basics" in card
    assert f'href="{MEET_URL}"' in card
    assert re.search(r'font-bold[^"]*">1</p><p[^>]*>Lectures today<', html)


@pytest.mark.django_db
def test_up_next_refresh_returns_the_card_alone(school) -> None:
    _set_status(_starting_in(school, 5, title="Algebra basics"), LectureStatus.LIVE)

    html = signed_in(school.student_1.user).get(reverse("student:up_next"))
    html = html.content.decode()

    assert html.lstrip().startswith('<div class="countdown-card')
    assert re.search(r"</svg>\s*Join</button>", html)
    assert "<html" not in html


@pytest.mark.django_db
def test_up_next_refresh_without_a_lecture_stops_polling(school) -> None:
    html = signed_in(school.teacher_1.user).get(reverse("teacher:up_next"))
    html = html.content.decode()

    assert "No upcoming lectures" in html
    assert "hx-get" not in html


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("name", "allowed"),
    [("teacher:up_next", Role.TEACHER), ("student:up_next", Role.STUDENT)],
)
def test_up_next_refresh_roles(institute_a, name, allowed) -> None:
    for role in (Role.INSTITUTE_ADMIN, Role.TEACHER, Role.STUDENT, Role.GUARDIAN):
        client = signed_in(
            make_user(email=f"{role}@example.com", role=role, institute=institute_a)
        )
        expected = 200 if role == allowed else 403
        assert client.get(reverse(name)).status_code == expected, role


@pytest.mark.django_db
def test_guardian_home_lists_upcoming_classes_with_the_child(school) -> None:
    link_guardian(school.student_2, "g1-a@example.com")
    add_lecture(school, title="Algebra basics")
    add_lecture(
        school,
        title="Evening physics",
        starts_at=soon(days=2),
        teacher=school.teacher_2,
        batch=school.evening,
        subjects=[school.physics],
    )
    dropped = add_lecture(school, title="Dropped", starts_at=soon(days=3))
    _set_status(dropped, LectureStatus.CANCELLED)

    html = _home(school.guardian_1.user, "guardian:home")

    rows = re.findall(r'class="lecture-row.*?</div></div>', html, re.S)
    texts = {re.sub(r"<[^>]+>", " ", row) for row in rows}
    algebra = next(text for text in texts if "Algebra basics" in text)
    physics = next(text for text in texts if "Evening physics" in text)
    assert str(school.student_1) in algebra and str(school.student_2) not in algebra
    assert str(school.student_2) in physics
    assert not any("Dropped" in text for text in texts)


@pytest.mark.django_db
def test_admin_dashboard_counts_lectures_today(school, institute_a) -> None:
    admin = make_user(
        email="admin@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_a
    )
    _starting_in(school, 0)

    html = _home(admin, "admin:home")

    assert re.search(r">Lectures today</dt><dd[^>]*>1</dd>", html)


# Time zone display


@pytest.mark.django_db
def test_page_clock_shows_the_viewer_zone(school) -> None:
    html = _home(school.teacher_1.user, "teacher:home")

    assert re.search(r'class="clock-zone[^"]*" title="Asia/Karachi">PKT<', html)
