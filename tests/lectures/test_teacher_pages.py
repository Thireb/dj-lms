"""Teacher lecture pages: My lectures, Create lecture, Edit (roadmap 3.1)."""

from __future__ import annotations

import re
from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from apps.core.roles import Role
from apps.lectures.models import Lecture
from django.urls import reverse
from django.utils import timezone

from tests.conftest import make_user, table_row
from tests.lectures.conftest import MEET_URL, add_lecture, signed_in, soon


def _url(action: str, pk: int | None = None) -> str:
    kwargs = {"pk": pk} if pk is not None else None
    return reverse(f"teacher:lecture_{action}", kwargs=kwargs)


def _form(school, **fields) -> dict:
    day = timezone.localtime(soon(days=2), ZoneInfo("Asia/Karachi")).date()
    data = {
        "title": "Algebra basics",
        "batch_subjects": [f"{school.morning.pk}:{school.math.pk}"],
        "date": day.isoformat(),
        "start_time": "10:00",
        "duration_minutes": "60",
        "delivery_mode": "manual_link",
        "meeting_url": MEET_URL,
    }
    data.update(fields)
    return data


def _evening_physics(school, **fields) -> Lecture:
    return add_lecture(
        school,
        teacher=school.teacher_2,
        batch=school.evening,
        subjects=[school.physics],
        **fields,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role", [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN, Role.STUDENT, Role.GUARDIAN]
)
@pytest.mark.parametrize("action", ["list", "create"])
def test_other_roles_get_403(institute_a, role, action) -> None:
    client = signed_in(
        make_user(email="x@example.com", role=role, institute=institute_a)
    )

    assert client.get(_url(action)).status_code == 403


@pytest.mark.django_db
def test_teacher_without_a_profile_cannot_create(institute_a) -> None:
    client = signed_in(
        make_user(email="new-t@example.com", role=Role.TEACHER, institute=institute_a)
    )

    assert client.get(_url("create")).status_code == 403
    assert client.get(_url("list")).status_code == 200  # an empty list


@pytest.mark.django_db
def test_list_shows_own_lectures_without_a_teacher_column(school) -> None:
    add_lecture(school, title="Mine")
    _evening_physics(school, title="Not mine")

    html = signed_in(school.teacher_1.user).get(_url("list")).content.decode()

    row = table_row(html, "Mine")
    assert "Not mine" not in html
    assert "cell-teacher" not in row
    assert f'href="{_url("edit", Lecture.unscoped.get(title="Mine").pk)}"' in row
    assert re.search(rf'href="{_url("list")}"[^>]*aria-current="page"', html)


@pytest.mark.django_db
def test_list_filters_offer_own_batches_only(school) -> None:
    html = signed_in(school.teacher_1.user).get(_url("list")).content.decode()

    assert f'<option value="{school.morning.pk}">Morning</option>' in html
    assert f'value="{school.evening.pk}"' not in html
    assert 'name="teacher"' not in html


@pytest.mark.django_db
def test_empty_list_invites_the_first_lecture(school) -> None:
    html = signed_in(school.teacher_1.user).get(_url("list")).content.decode()

    assert "Create your first lecture" in html


@pytest.mark.django_db
def test_create_form_has_no_teacher_choice(school) -> None:
    html = signed_in(school.teacher_1.user).get(_url("create")).content.decode()

    assert 'name="teacher"' not in html
    assert f'value="{school.morning.pk}:{school.math.pk}"' in html
    assert f'value="{school.evening.pk}:{school.physics.pk}"' not in html


@pytest.mark.django_db
def test_create_always_uses_the_signed_in_teacher(school) -> None:
    client = signed_in(school.teacher_1.user)

    response = client.post(_url("create"), _form(school, teacher=school.teacher_2.pk))

    assert response.status_code == 302
    assert response["Location"] == _url("list")
    # unscoped: test assertion outside a tenant context.
    assert Lecture.unscoped.get().teacher == school.teacher_1


@pytest.mark.django_db
def test_teacher_cannot_use_another_teacher_pair(school) -> None:
    pair = f"{school.evening.pk}:{school.physics.pk}"
    html = (
        signed_in(school.teacher_1.user)
        .post(_url("create"), _form(school, batch_subjects=[pair]))
        .content.decode()
    )

    assert "Select a valid choice." in html
    assert not Lecture.unscoped.exists()


@pytest.mark.django_db
def test_teacher_edits_own_lecture(school) -> None:
    lecture = add_lecture(school)
    client = signed_in(school.teacher_1.user)

    response = client.post(
        _url("edit", lecture.pk),
        _form(school, title="Moved", date=(timezone.localdate() + timedelta(days=3))),
    )

    lecture.refresh_from_db()
    assert response.status_code == 302
    assert lecture.title == "Moved"


@pytest.mark.django_db
def test_teacher_cannot_open_another_teacher_lecture(school) -> None:
    other = _evening_physics(school)
    client = signed_in(school.teacher_1.user)

    assert client.get(_url("edit", other.pk)).status_code == 404
    assert client.post(_url("edit", other.pk), _form(school)).status_code == 404
