"""Roadmap 6.1: the bell, its count and panel, the Notifications page,
Open and Mark all as read, and the switches on My profile."""

from __future__ import annotations

from datetime import timedelta

import pytest
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.notifications.models import Notification
from apps.notifications.services import notify, unread_count
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from tests.conftest import make_user
from tests.notifications.conftest import send

LIST = reverse("notifications:list")
COUNT = reverse("notifications:count")
PANEL = reverse("notifications:panel")
READ_ALL = reverse("notifications:read_all")


def signed_in(user) -> Client:
    client = Client()
    client.force_login(user)
    return client


def _open(row) -> str:
    return reverse("notifications:open", kwargs={"pk": row.pk})


def _mine(user):
    # unscoped: test assertion outside a tenant context.
    return Notification.unscoped.filter(user=user)


# The bell


@pytest.mark.django_db
def test_every_portal_shows_the_bell(people) -> None:
    for name, home in (("teacher", "teacher:home"), ("admin", "admin:home")):
        html = signed_in(people[name]).get(reverse(home)).content.decode()
        assert f'href="{LIST}"' in html and 'class="notification-bell icon-btn"' in html
        assert f'hx-get="{COUNT}"' in html and 'hx-trigger="load, every 60s"' in html
        assert f'hx-get="{PANEL}"' in html


@pytest.mark.django_db
def test_super_admin_has_no_bell() -> None:
    boss = make_user(email="super@example.com", role=Role.SUPER_ADMIN)
    html = signed_in(boss).get(reverse("super:institute_list")).content.decode()
    assert "notification-bell" not in html
    assert signed_in(boss).get(COUNT).status_code == 403


@pytest.mark.django_db
def test_count_shows_the_unread_number(people, institute_a) -> None:
    teacher = people["teacher"]
    client = signed_in(teacher)
    html = client.get(COUNT).content.decode()
    assert "Notifications</span>" in html and "unread" not in html
    send(institute_a, [teacher])
    send(institute_a, [teacher])
    send(institute_a, [people["student"]])
    html = client.get(COUNT).content.decode()
    assert "Notifications, 2 unread" in html and ">2</span>" in html
    with tenant_context(institute_a):
        notify([teacher] * 1, "new_message", "x")
        for _ in range(100):
            notify([teacher], "new_message", "x")
    assert ">99+</span>" in client.get(COUNT).content.decode()


@pytest.mark.django_db
def test_signed_out_bell_parts_are_empty() -> None:
    """HTMX must not swap the sign-in page into the bell."""
    for url in (COUNT, PANEL):
        response = Client().get(url)
        assert (response.status_code, response.content) == (204, b"")


@pytest.mark.django_db
def test_panel_lists_the_latest_eight(people, institute_a) -> None:
    teacher = people["teacher"]
    start = timezone.now()
    for n in range(10):
        send(institute_a, [teacher], text=f"Note {n}", now=start + timedelta(minutes=n))
    send(institute_a, [people["student"]], text="Not yours")
    read = _mine(teacher).get(text="Note 9")
    read.read_at = timezone.now()
    read.save()
    response = signed_in(teacher).get(
        PANEL, HTTP_HX_CURRENT_URL="http://testserver/teacher/lectures/?tab=past"
    )
    html = response.content.decode()
    assert [f"Note {n}" in html for n in range(10)] == [False] * 2 + [True] * 8
    assert "Not yours" not in html
    assert html.count("Unread: ") == 7
    assert f'action="{_open(read)}"' in html
    assert 'name="csrfmiddlewaretoken"' in html
    assert 'name="next" value="/teacher/lectures/?tab=past"' in html
    assert f'href="{LIST}"' in html


@pytest.mark.django_db
def test_panel_escapes_the_text_and_has_an_empty_state(people, institute_a) -> None:
    teacher = people["teacher"]
    assert "No notifications yet." in signed_in(teacher).get(PANEL).content.decode()
    send(institute_a, [teacher], text="<b>Hi</b>")
    html = signed_in(teacher).get(PANEL).content.decode()
    assert "&lt;b&gt;Hi&lt;/b&gt;" in html and "<b>Hi" not in html


# Open and Mark all as read


@pytest.mark.django_db
def test_open_marks_read_and_follows_the_link(people, institute_a) -> None:
    teacher = people["teacher"]
    send(institute_a, [teacher], text="With link", link="/teacher/lectures/")
    send(institute_a, [teacher], text="No link")
    client = signed_in(teacher)
    with_link, no_link = (
        _mine(teacher).get(text="With link"),
        _mine(teacher).get(text="No link"),
    )
    assert client.get(_open(with_link)).status_code == 405
    response = client.post(_open(with_link))
    assert response["Location"] == "/teacher/lectures/"
    assert client.post(_open(no_link))["Location"] == LIST
    with tenant_context(institute_a):
        assert unread_count(teacher) == 0


@pytest.mark.django_db
def test_open_refuses_another_users_notification(people, institute_a) -> None:
    send(institute_a, [people["student"]])
    theirs = _mine(people["student"]).get()
    assert signed_in(people["teacher"]).post(_open(theirs)).status_code == 404
    assert signed_in(people["other"]).post(_open(theirs)).status_code == 404
    assert _mine(people["student"]).get().read_at is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("next_url", "goes_to"),
    [
        ("/teacher/lectures/?tab=past", "/teacher/lectures/?tab=past"),
        ("https://evil.example/teacher/", "/teacher/"),  # the host is dropped
        ("//evil.example/x", "/x"),
        ("/\\evil.example/x", LIST),
        ("/teacher/\r\nSet-Cookie: x=1", LIST),
        ("", LIST),
        ("javascript:alert(1)", LIST),
    ],
)
def test_mark_all_read_goes_back_on_this_site(people, institute_a, next_url, goes_to):
    teacher = people["teacher"]
    send(institute_a, [teacher])
    send(institute_a, [people["student"]])
    response = signed_in(teacher).post(READ_ALL, {"next": next_url})
    assert response["Location"] == goes_to
    with tenant_context(institute_a):
        assert unread_count(teacher) == 0
        assert unread_count(people["student"]) == 1


@pytest.mark.django_db
def test_mark_all_read_needs_the_csrf_token(people, institute_a) -> None:
    send(institute_a, [people["teacher"]])
    client = Client(enforce_csrf_checks=True)
    client.force_login(people["teacher"])
    assert client.post(READ_ALL).status_code == 403


# The Notifications page


@pytest.mark.django_db
def test_list_page_for_every_role(people, institute_a) -> None:
    guardian = make_user(
        email="g1@example.com", role=Role.GUARDIAN, institute=institute_a
    )
    sub = make_user(email="sub@example.com", role=Role.SUB_ADMIN, institute=institute_a)
    for user in (people["teacher"], people["student"], people["admin"], guardian, sub):
        response = signed_in(user).get(LIST)
        assert response.status_code == 200, user.role
        assert "No notifications yet." in response.content.decode()
    assert Client().get(LIST).status_code == 302


@pytest.mark.django_db
def test_list_page_shows_new_and_mark_all(people, institute_a) -> None:
    teacher = people["teacher"]
    send(institute_a, [teacher], text="Physics is cancelled.")
    send(institute_a, [people["other"]], text="Other institute")
    html = signed_in(teacher).get(LIST).content.decode()
    assert "Physics is cancelled." in html and "Other institute" not in html
    assert "New" in html and f'action="{READ_ALL}"' in html
    signed_in(teacher).post(READ_ALL)
    html = signed_in(teacher).get(LIST).content.decode()
    assert f'action="{READ_ALL}"' not in html


# My profile switches (SPEC 4.22)


@pytest.mark.django_db
def test_profile_shows_the_switches_by_role(people) -> None:
    profile = reverse("accounts:profile")
    student = signed_in(people["student"]).get(profile).content.decode()
    assert 'name="class_alerts"' in student and 'name="fee_alerts"' in student
    teacher = signed_in(people["teacher"]).get(profile).content.decode()
    assert 'name="class_alerts"' in teacher and 'name="fee_alerts"' not in teacher


@pytest.mark.django_db
def test_switching_class_alerts_off_stops_them(people, institute_a) -> None:
    student = people["student"]
    response = signed_in(student).post(
        reverse("accounts:profile"),
        {"first_name": "Sam", "last_name": "Sample", "fee_alerts": "on"},
    )
    assert response.status_code == 302
    student.refresh_from_db()
    assert (student.class_alerts, student.fee_alerts) == (False, True)
    assert send(institute_a, [student], event="lecture_cancelled") == 0
    assert send(institute_a, [student], event="challan_due") == 1


@pytest.mark.django_db
def test_profile_service_changes_only_the_switches(people) -> None:
    from apps.accounts.services import update_profile

    teacher = people["teacher"]
    update_profile(
        teacher,
        first_name="Tia",
        last_name="Test",
        phone="",
        timezone="",
        alerts={"class_alerts": False, "role": Role.INSTITUTE_ADMIN, "is_staff": True},
    )
    teacher.refresh_from_db()
    assert teacher.class_alerts is False
    assert (teacher.role, teacher.is_staff) == (Role.TEACHER, False)
