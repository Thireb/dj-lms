"""Student enrolment, edit and status (roadmap 2.5b, SPEC 4.1)."""

from __future__ import annotations

import datetime

import pytest
from apps.academics.models import ClassLabel, StudentBatchSubject
from apps.accounts.models import User
from apps.core.roles import Role
from apps.core.tenancy import TenantContextError, tenant_context
from apps.people.models import GuardianStudentLink, StudentProfile
from apps.people.services import (
    EMAIL_TAKEN,
    NEW_GUARDIAN_PASSWORD,
    SAME_EMAILS,
    StudentDetails,
    enrol_student,
    set_student_active,
    update_student,
)
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError

from tests.conftest import (
    TEST_INVALID_PASSWORD_FOR_VALIDATION,
    TEST_LOGIN_PASSWORD,
    TEST_NEW_PASSWORD,
)
from tests.school import make_lists

DETAILS = StudentDetails(
    full_name="Alex  Sample",
    phone="0300-4444444",
    guardian_phone="0300-5555555",
    father_name=" Sam Sample ",
    cnic="3520200000002",
    date_of_birth=datetime.date(2012, 5, 1),
    gender="male",
    address="House 1",
    city="Lahore",
)


def _enrol(school, details=DETAILS, **fields) -> StudentProfile:
    institute = school.morning.institute
    values = {
        "email": "Alex@Example.com",
        "password": TEST_LOGIN_PASSWORD,
        "selections": {school.morning: [school.math]},
        "guardian_name": "Sam Sample",
        "guardian_email": "parent@example.com",
        "guardian_password": TEST_NEW_PASSWORD,
    }
    values.update(fields)
    with tenant_context(institute):
        return enrol_student(institute, details, **values)


def _nothing_saved() -> bool:
    emails = ["alex@example.com", "parent@example.com"]
    return not User.objects.filter(email__in=emails).exists()


@pytest.mark.django_db
def test_enrol_creates_student_links_and_guardian(school) -> None:
    student = _enrol(school)

    user = student.user
    assert (user.role, user.email) == (Role.STUDENT, "alex@example.com")
    assert user.get_full_name() == "Alex Sample"
    assert authenticate(username=user.email, password=TEST_LOGIN_PASSWORD) == user
    assert student.student_code == "STU-004"  # the school fixture made three
    assert student.father_name == "Sam Sample"
    assert student.date_of_birth == datetime.date(2012, 5, 1)
    assert student.guardian_phone == "0300-5555555"
    # unscoped: test assertions outside a tenant context.
    pairs = StudentBatchSubject.unscoped.filter(student=student)
    assert [(p.batch.name, p.subject.name) for p in pairs] == [("Morning", "Math")]
    link = GuardianStudentLink.unscoped.get(student=student)
    guardian = link.guardian.user
    assert (guardian.email, guardian.get_full_name()) == (
        "parent@example.com",
        "Sam Sample",
    )
    assert guardian.phone == "0300-5555555"
    assert authenticate(username=guardian.email, password=TEST_NEW_PASSWORD)


@pytest.mark.django_db
def test_second_child_links_existing_guardian_without_password(school) -> None:
    first = _enrol(school)
    second = _enrol(
        school,
        email="sibling@example.com",
        guardian_email="PARENT@example.com",
        guardian_password="",
    )

    # unscoped: test assertions outside a tenant context.
    first_guardian = GuardianStudentLink.unscoped.get(student=first).guardian
    second_guardian = GuardianStudentLink.unscoped.get(student=second).guardian
    assert first_guardian == second_guardian


@pytest.mark.django_db
def test_new_guardian_needs_a_password(school) -> None:
    with pytest.raises(ValidationError) as error:
        _enrol(school, guardian_password="")

    assert error.value.message_dict == {"guardian_password": [NEW_GUARDIAN_PASSWORD]}
    assert _nothing_saved()


@pytest.mark.django_db
def test_student_and_guardian_emails_must_differ(school) -> None:
    with pytest.raises(ValidationError) as error:
        _enrol(school, guardian_email=" alex@EXAMPLE.com")

    assert error.value.message_dict == {"guardian_email": [SAME_EMAILS]}
    assert _nothing_saved()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("fields", "key"),
    [
        ({"email": "t1-a@example.com"}, "email"),
        ({"password": TEST_INVALID_PASSWORD_FOR_VALIDATION}, "password"),
        ({"selections": {}}, "batch_subjects"),
        ({"guardian_email": "t1-a@example.com"}, "guardian_email"),
        (
            {"guardian_password": TEST_INVALID_PASSWORD_FOR_VALIDATION},
            "guardian_password",
        ),
    ],
)
def test_any_error_saves_nothing(school, fields, key) -> None:
    with pytest.raises(ValidationError) as error:
        _enrol(school, **fields)

    assert key in error.value.message_dict
    assert _nothing_saved()
    # unscoped: test assertion outside a tenant context.
    assert not StudentProfile.unscoped.filter(student_code="STU-004").exists()


@pytest.mark.django_db
def test_failed_enrol_does_not_use_a_student_code(school) -> None:
    with pytest.raises(ValidationError):
        _enrol(school, guardian_password="")

    assert _enrol(school).student_code == "STU-004"


@pytest.mark.django_db
def test_class_label_of_other_institute_is_rejected(school, institute_b) -> None:
    (label_b,) = make_lists(institute_b, ClassLabel, "Grade 9")
    details = StudentDetails(**{**DETAILS.__dict__, "class_label": label_b})

    with pytest.raises(ValidationError) as error:
        _enrol(school, details=details)

    assert "class_label" in error.value.message_dict
    assert _nothing_saved()


@pytest.mark.django_db
def test_update_student_changes_details_and_pairs(school) -> None:
    student = school.student_1
    details = StudentDetails(
        full_name="Jamie Example",
        phone="0311-1111111",
        guardian_phone="0311-2222222",
        class_label=school.grade_9,
        city="Karachi",
    )
    with tenant_context(student.institute):
        update_student(
            student,
            details,
            email="Jamie@Example.com",
            selections={school.evening: [school.physics]},
        )

    # unscoped: test assertions outside a tenant context.
    saved = StudentProfile.unscoped.select_related("user").get(pk=student.pk)
    assert saved.user.email == "jamie@example.com"
    assert saved.user.get_full_name() == "Jamie Example"
    assert (saved.class_label, saved.city) == (school.grade_9, "Karachi")
    pairs = StudentBatchSubject.unscoped.filter(student=student)
    assert [(p.batch.name, p.subject.name) for p in pairs] == [("Evening", "Physics")]
    assert GuardianStudentLink.unscoped.filter(student=student).count() == 1


@pytest.mark.django_db
def test_update_rejects_email_of_another_account(school) -> None:
    student = school.student_1
    with tenant_context(student.institute), pytest.raises(ValidationError) as error:
        update_student(
            student,
            DETAILS,
            email="g1-a@example.com",
            selections={school.morning: [school.math]},
        )

    assert error.value.message_dict == {"email": [EMAIL_TAKEN]}


@pytest.mark.django_db
def test_student_status_changes_sign_in_but_not_guardian(school) -> None:
    student = school.student_1
    with tenant_context(student.institute):
        set_student_active(student, is_active=False)

    student.refresh_from_db()
    assert student.status == "inactive"
    assert User.objects.get(pk=student.user_id).is_active is False
    assert User.objects.get(pk=school.guardian_1.user_id).is_active is True

    with tenant_context(student.institute):
        set_student_active(student, is_active=True)

    assert User.objects.get(pk=student.user_id).is_active is True


@pytest.mark.django_db
def test_student_services_need_tenant_context(school) -> None:
    with pytest.raises(TenantContextError):
        enrol_student(
            school.morning.institute,
            DETAILS,
            email="alex@example.com",
            password=TEST_LOGIN_PASSWORD,
            selections={school.morning: [school.math]},
            guardian_name="Sam",
            guardian_email="parent@example.com",
            guardian_password=TEST_NEW_PASSWORD,
        )
    with pytest.raises(TenantContextError):
        set_student_active(school.student_1, is_active=False)
