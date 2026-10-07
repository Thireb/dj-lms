"""Admin student pages (roadmap 2.5b, SPEC 3 All Students and 4.1)."""

from __future__ import annotations

import re

import pytest
from apps.academics.models import ClassLabel, StudentBatchSubject
from apps.accounts.models import User
from apps.core.roles import Role
from apps.people.models import GuardianStudentLink, StudentProfile
from django.test import Client
from django.urls import reverse

from tests.conftest import TEST_LOGIN_PASSWORD, TEST_NEW_PASSWORD, make_user
from tests.school import make_lists


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
    return reverse(f"admin:student_{action}", kwargs=kwargs)


def _codes(response) -> list[str]:
    return re.findall(r">(STU-\d+)<", response.content.decode())


def _form(school, **fields) -> dict:
    data = {
        "full_name": "Alex Sample",
        "guardian_phone": "0300-5555555",
        "email": "alex@example.com",
        "password": TEST_LOGIN_PASSWORD,
        "guardian_name": "Sam Sample",
        "guardian_email": "parent@example.com",
        "guardian_password": TEST_NEW_PASSWORD,
        "batch_subjects": [f"{school.morning.pk}:{school.math.pk}"],
    }
    data.update(fields)
    return data


# List


@pytest.mark.django_db
def test_empty_list_shows_one_action(admin_client) -> None:
    html = admin_client.get(_url("list")).content.decode()

    assert "No students yet." in html
    assert "Enrol your first student" in html


@pytest.mark.django_db
def test_list_shows_class_batches_and_guardian(admin_client, school) -> None:
    student = school.student_1
    student.class_label = school.grade_9
    student.save()

    html = admin_client.get(_url("list")).content.decode()

    row = re.search(r">STU-001</td>(.*?)</tr>", html, re.S).group(1)
    assert ">Grade 9<" in row
    assert ">Morning<" in row
    assert "g1-a@example.com" in row
    assert html.count(">STU-001<") == 1  # institute B's STU-001 is hidden


@pytest.mark.django_db
def test_filters(admin_client, school) -> None:
    student = school.student_2
    student.class_label = school.grade_9
    student.save()
    admin_client.post(_url("status", school.student_1.pk), {"action": "deactivate"})

    assert _codes(admin_client.get(_url("list"), {"batch": school.evening.pk})) == [
        "STU-002"
    ]
    assert _codes(
        admin_client.get(_url("list"), {"class_label": school.grade_9.pk})
    ) == ["STU-002"]
    assert _codes(admin_client.get(_url("list"), {"status": "inactive"})) == ["STU-001"]
    assert _codes(admin_client.get(_url("list"), {"q": "s3-a"})) == ["STU-003"]
    guardian_phone = admin_client.get(_url("list"), {"q": "0300-0000000"})
    assert len(_codes(guardian_phone)) == 3


@pytest.mark.django_db
def test_class_filter_lists_own_classes_only(admin_client, school, institute_b):
    (label_b,) = make_lists(institute_b, ClassLabel, "Other class")

    html = admin_client.get(_url("list")).content.decode()

    assert ">Grade 9</option>" in html
    assert "Other class" not in html
    assert f'value="{label_b.pk}"' not in html


# Enrol


@pytest.mark.django_db
def test_enrol_page_has_all_sections(admin_client, school) -> None:
    html = admin_client.get(_url("create")).content.decode()

    for text in ["Personal", "Contact", "Academic", "Sign-in", "Guardian password"]:
        assert text in html
    assert ">Grade 9</option>" in html
    assert html.count('type="password"') == 2


@pytest.mark.django_db
def test_enrol_creates_student_and_guardian(admin_client, school) -> None:
    data = _form(school, class_label=school.grade_9.pk, gender="female")
    response = admin_client.post(_url("create"), data, follow=True)

    student = StudentProfile.unscoped.get(user__email="alex@example.com")
    assert response.redirect_chain[-1][0] == _url("list")
    assert "Student enrolled." in response.content.decode()
    assert (student.class_label, student.gender) == (school.grade_9, "female")
    assert GuardianStudentLink.unscoped.get(student=student).guardian.user.email == (
        "parent@example.com"
    )


@pytest.mark.django_db
def test_enrol_links_existing_guardian(admin_client, school) -> None:
    data = _form(school, guardian_email="G1-A@example.com", guardian_password="")

    admin_client.post(_url("create"), data)

    student = StudentProfile.unscoped.get(user__email="alex@example.com")
    link = GuardianStudentLink.unscoped.get(student=student)
    assert link.guardian == school.guardian_1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"batch_subjects": []}, "Choose at least one batch."),
        ({"guardian_password": ""}, "Enter a password for the new guardian."),
        (
            {"guardian_email": "alex@example.com"},
            "The student and guardian emails must be different.",
        ),
        ({"email": "t1-a@example.com"}, "This email is already used by another"),
        ({"cnic": "1234"}, "CNIC must be exactly 13 digits."),
        ({"guardian_phone": ""}, "This field is required."),
    ],
)
def test_enrol_errors_save_nothing(admin_client, school, fields, message) -> None:
    response = admin_client.post(_url("create"), _form(school, **fields))

    assert response.status_code == 200
    assert message in response.content.decode()
    assert not User.objects.filter(email="alex@example.com").exists()


@pytest.mark.django_db
def test_enrol_rejects_class_of_other_institute(
    admin_client, school, institute_b
) -> None:
    (label_b,) = make_lists(institute_b, ClassLabel, "Other class")

    response = admin_client.post(_url("create"), _form(school, class_label=label_b.pk))

    assert "Select a valid choice." in response.content.decode()
    assert not User.objects.filter(email="alex@example.com").exists()


@pytest.mark.django_db
def test_inactive_class_is_not_offered_on_enrol(admin_client, school) -> None:
    ClassLabel.unscoped.filter(pk=school.grade_9.pk).update(is_active=False)

    assert ">Grade 9</option>" not in admin_client.get(_url("create")).content.decode()


# Edit


@pytest.mark.django_db
def test_edit_shows_values_and_keeps_inactive_class(admin_client, school) -> None:
    student = school.student_1
    student.class_label = school.grade_9
    student.save()
    ClassLabel.unscoped.filter(pk=school.grade_9.pk).update(is_active=False)

    html = admin_client.get(_url("edit", student.pk)).content.decode()

    assert 'value="s1-a@example.com"' in html
    assert re.search(rf'<option value="{school.grade_9.pk}" selected>Grade 9', html)
    assert 'name="password"' not in html
    assert 'name="guardian_email"' not in html


@pytest.mark.django_db
def test_edit_saves_changes(admin_client, school) -> None:
    student = school.student_1
    data = {
        "full_name": "Jamie Example",
        "guardian_phone": "0311-2222222",
        "email": "jamie@example.com",
        "batch_subjects": [f"{school.evening.pk}:{school.physics.pk}"],
    }

    response = admin_client.post(_url("edit", student.pk), data, follow=True)

    student.refresh_from_db()
    student.user.refresh_from_db()
    assert "Student saved." in response.content.decode()
    assert student.user.email == "jamie@example.com"
    assert student.guardian_phone == "0311-2222222"
    pairs = StudentBatchSubject.unscoped.filter(student=student)
    assert [(p.batch.name, p.subject.name) for p in pairs] == [("Evening", "Physics")]


@pytest.mark.django_db
def test_other_institute_student_is_404(admin_client, school) -> None:
    other = school.student_b

    assert admin_client.get(_url("edit", other.pk)).status_code == 404
    edit = admin_client.post(_url("edit", other.pk), _form(school))
    status = admin_client.post(_url("status", other.pk), {"action": "deactivate"})

    assert (edit.status_code, status.status_code) == (404, 404)
    other.user.refresh_from_db()
    assert other.user.is_active is True


# Status and access


@pytest.mark.django_db
def test_deactivated_student_is_signed_out(admin_client, school) -> None:
    student_client = Client()
    student_client.force_login(school.student_1.user)

    response = admin_client.post(
        _url("status", school.student_1.pk), {"action": "deactivate"}, follow=True
    )
    after = student_client.get(reverse("accounts:profile"))

    assert "deactivated." in response.content.decode()
    assert after.status_code == 302
    assert after["Location"].startswith(reverse("accounts:login"))


@pytest.mark.django_db
@pytest.mark.parametrize("role", [Role.TEACHER, Role.STUDENT, Role.GUARDIAN])
@pytest.mark.parametrize("action", ["list", "create"])
def test_other_roles_get_403(client, institute_a, role, action) -> None:
    client.force_login(
        make_user(email="x@example.com", role=role, institute=institute_a)
    )

    assert client.get(_url(action)).status_code == 403


@pytest.mark.django_db
def test_sub_admin_without_people_menu_gets_403(client, institute_a) -> None:
    client.force_login(
        make_user(email="sub@example.com", role=Role.SUB_ADMIN, institute=institute_a)
    )

    assert client.get(_url("list")).status_code == 403
