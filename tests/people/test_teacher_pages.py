"""Admin teacher pages (roadmap 2.5a, SPEC 3 All Teachers and 4.2)."""

from __future__ import annotations

import re

import pytest
from apps.academics.models import Batch, Subject, TeacherBatchSubject
from apps.accounts.models import User
from apps.core.roles import Role
from apps.people.models import TeacherProfile
from django.test import Client
from django.urls import reverse

from tests.conftest import TEST_LOGIN_PASSWORD, make_user
from tests.people.conftest import teacher
from tests.school import link_teacher, make_lists


@pytest.fixture
def admin_client(client: Client, institute_a) -> Client:
    client.force_login(
        make_user(
            email="admin-a@example.com",
            role=Role.INSTITUTE_ADMIN,
            institute=institute_a,
        )
    )
    return client


def _url(action: str, pk: int | None = None) -> str:
    kwargs = {"pk": pk} if pk is not None else None
    return reverse(f"admin:teacher_{action}", kwargs=kwargs)


def _pair(batch, subject) -> str:
    return f"{batch.pk}:{subject.pk}"


def _form(school, **fields) -> dict:
    data = {
        "full_name": "Robin Example",
        "phone": "0300-3333333",
        "email": "robin@example.com",
        "password": TEST_LOGIN_PASSWORD,
        "batch_subjects": [_pair(school.evening, school.math)],
    }
    data.update(fields)
    return data


def _pairs(teacher) -> set:
    # unscoped: test assertion outside a tenant context.
    links = TeacherBatchSubject.unscoped.filter(teacher=teacher)
    return {(link.batch.name, link.subject.name) for link in links}


# List


@pytest.mark.django_db
def test_empty_list_shows_one_action(admin_client) -> None:
    html = admin_client.get(_url("list")).content.decode()

    assert "No teachers yet." in html
    assert "Add your first teacher" in html


@pytest.mark.django_db
def test_list_shows_own_teachers_with_batches(admin_client, school) -> None:
    html = admin_client.get(_url("list")).content.decode()

    assert re.search(r">TCH-001</td>.*?>Morning</td><td[^>]*>Math</td>", html, re.S)
    assert "TCH-002" in html
    assert school.teacher_b.teacher_code == "TCH-001"
    assert html.count(">TCH-001<") == 1  # institute B's TCH-001 is hidden


@pytest.mark.django_db
def test_search_matches_name_code_email_and_phone(admin_client, school) -> None:
    user = school.teacher_2.user
    user.first_name, user.phone = "Jordan", "0399-1234567"
    user.save()

    for term in ["jordan", "TCH-002", "t2-a@", "1234567"]:
        html = admin_client.get(_url("list"), {"q": term}).content.decode()
        assert ">TCH-002<" in html, term
        assert ">TCH-001<" not in html, term


@pytest.mark.django_db
def test_batch_and_status_filters(admin_client, school) -> None:
    by_batch = admin_client.get(_url("list"), {"batch": school.evening.pk})
    admin_client.post(_url("status", school.teacher_1.pk), {"action": "deactivate"})
    inactive = admin_client.get(_url("list"), {"status": "inactive"})

    assert re.findall(r">(TCH-\d+)<", by_batch.content.decode()) == ["TCH-002"]
    assert re.findall(r">(TCH-\d+)<", inactive.content.decode()) == ["TCH-001"]


@pytest.mark.django_db
def test_bad_filter_values_are_ignored(admin_client, school) -> None:
    response = admin_client.get(_url("list"), {"batch": "x'1", "status": "gone"})

    assert response.status_code == 200
    assert len(re.findall(r">(TCH-\d+)<", response.content.decode())) == 3


@pytest.mark.django_db
def test_filter_dropdowns_list_own_batches_only(admin_client, school) -> None:
    html = admin_client.get(_url("list"), {"batch": school.morning.pk}).content
    html = html.decode()

    assert f'<option value="{school.morning.pk}" selected>Morning</option>' in html
    assert f'value="{school.batch_b.pk}"' not in html


@pytest.mark.django_db
def test_pagination_keeps_filters(admin_client, school, institute_a) -> None:
    for number in range(26):
        profile = teacher(institute_a, f"extra{number}@example.com")
        link_teacher(profile, {school.evening: [school.physics]})

    html = admin_client.get(
        _url("list"), {"batch": school.evening.pk, "status": "active"}
    ).content.decode()

    assert f"batch={school.evening.pk}&amp;status=active&page=2" in html


# Create


@pytest.mark.django_db
def test_create_page_groups_subjects_by_batch(admin_client, school) -> None:
    Batch.unscoped.filter(pk=school.evening.pk).update(is_active=False)

    html = admin_client.get(_url("create")).content.decode()

    assert "<legend" in html and ">Morning</legend>" in html
    assert ">Evening</legend>" not in html  # inactive batches are not offered
    assert f'value="{_pair(school.morning, school.physics)}"' in html
    assert 'type="password"' in html


@pytest.mark.django_db
def test_create_adds_teacher(admin_client, school) -> None:
    response = admin_client.post(_url("create"), _form(school), follow=True)

    teacher = TeacherProfile.unscoped.get(user__email="robin@example.com")
    assert response.redirect_chain[-1][0] == _url("list")
    assert "Teacher added." in response.content.decode()
    assert teacher.user.get_full_name() == "Robin Example"
    assert _pairs(teacher) == {("Evening", "Math")}


@pytest.mark.django_db
def test_create_needs_a_batch(admin_client, school) -> None:
    response = admin_client.post(_url("create"), _form(school, batch_subjects=[]))

    assert "Choose at least one batch." in response.content.decode()
    assert not User.objects.filter(email="robin@example.com").exists()


@pytest.mark.django_db
def test_create_rejects_pair_of_other_institute(
    admin_client, school, institute_b
) -> None:
    (subject_b,) = make_lists(institute_b, Subject, "Night")
    tampered = _form(school, batch_subjects=[f"{school.batch_b.pk}:{subject_b.pk}"])

    response = admin_client.post(_url("create"), tampered)

    assert "Select a valid choice." in response.content.decode()
    assert not User.objects.filter(email="robin@example.com").exists()


@pytest.mark.django_db
def test_create_shows_email_taken(admin_client, school) -> None:
    response = admin_client.post(
        _url("create"), _form(school, email="T2-A@example.com")
    )

    assert "This email is already used by another account." in (
        response.content.decode()
    )


@pytest.mark.django_db
def test_create_rejects_bad_cnic(admin_client, school) -> None:
    response = admin_client.post(_url("create"), _form(school, cnic="35202-1"))

    assert "CNIC must be exactly 13 digits." in response.content.decode()


# Edit


@pytest.mark.django_db
def test_edit_shows_current_values(admin_client, school) -> None:
    teacher = school.teacher_1
    html = admin_client.get(_url("edit", teacher.pk)).content.decode()

    assert 'value="t1-a@example.com"' in html
    assert f'value="{_pair(school.morning, school.math)}"' in html
    checked = re.search(
        rf'value="{_pair(school.morning, school.math)}"[^>]*checked', html
    )
    assert checked
    assert 'name="password"' not in html


@pytest.mark.django_db
def test_edit_keeps_inactive_pair_already_linked(admin_client, school) -> None:
    Batch.unscoped.filter(pk=school.morning.pk).update(is_active=False)
    teacher = school.teacher_1
    pair = _pair(school.morning, school.math)

    html = admin_client.get(_url("edit", teacher.pk)).content.decode()
    response = admin_client.post(
        _url("edit", teacher.pk), _form(school, batch_subjects=[pair])
    )

    assert f'value="{pair}"' in html
    assert response.status_code == 302
    assert _pairs(teacher) == {("Morning", "Math")}


@pytest.mark.django_db
def test_edit_saves_changes(admin_client, school) -> None:
    teacher = school.teacher_1
    data = _form(school, batch_subjects=[_pair(school.evening, school.physics)])

    admin_client.post(_url("edit", teacher.pk), data)

    teacher.user.refresh_from_db()
    assert teacher.user.email == "robin@example.com"
    assert _pairs(teacher) == {("Evening", "Physics")}


@pytest.mark.django_db
def test_other_institute_teacher_is_404(admin_client, school) -> None:
    other = school.teacher_b

    assert admin_client.get(_url("edit", other.pk)).status_code == 404
    edit = admin_client.post(_url("edit", other.pk), _form(school))
    status = admin_client.post(_url("status", other.pk), {"action": "deactivate"})

    assert edit.status_code == 404
    assert status.status_code == 404
    other.user.refresh_from_db()
    assert other.user.is_active is True


# Status and access


@pytest.mark.django_db
def test_deactivated_teacher_is_signed_out_and_cannot_sign_in(
    admin_client, school
) -> None:
    teacher_client = Client()
    teacher_client.force_login(school.teacher_1.user)

    response = admin_client.post(
        _url("status", school.teacher_1.pk), {"action": "deactivate"}, follow=True
    )
    after = teacher_client.get(reverse("accounts:profile"))
    login = Client().post(
        reverse("accounts:login"),
        {"email": "t1-a@example.com", "password": TEST_LOGIN_PASSWORD},
    )

    assert "deactivated." in response.content.decode()
    assert after.status_code == 302
    assert after["Location"].startswith(reverse("accounts:login"))
    assert login.status_code == 200  # the form is shown again, no redirect


@pytest.mark.django_db
def test_unknown_status_action_changes_nothing(admin_client, school) -> None:
    admin_client.post(_url("status", school.teacher_1.pk), {"action": "delete"})

    school.teacher_1.user.refresh_from_db()
    assert school.teacher_1.user.is_active is True


@pytest.mark.django_db
def test_sub_admin_without_people_menu_gets_403(client, institute_a) -> None:
    client.force_login(
        make_user(email="sub@example.com", role=Role.SUB_ADMIN, institute=institute_a)
    )

    assert client.get(_url("list")).status_code == 403
