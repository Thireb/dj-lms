"""Teacher accounts: create, update and status (roadmap 2.5a, SPEC 4.2)."""

from __future__ import annotations

import pytest
from apps.academics.models import TeacherBatchSubject
from apps.accounts.models import User
from apps.core.roles import Role
from apps.core.tenancy import TenantContextError, tenant_context
from apps.people.models import TeacherProfile
from apps.people.services import (
    EMAIL_TAKEN,
    create_teacher,
    set_teacher_active,
    split_full_name,
    update_teacher,
)
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError

from tests.conftest import (
    TEST_INVALID_PASSWORD_FOR_VALIDATION,
    TEST_LOGIN_PASSWORD,
    make_user,
)


def _create(school, **fields) -> TeacherProfile:
    institute = school.morning.institute
    values = {
        "full_name": "Sam  Ali Sample",
        "email": " New.Teacher@Example.com",
        "password": TEST_LOGIN_PASSWORD,
        "phone": "0300-2222222",
        "selections": {school.morning: [school.math, school.physics]},
    }
    values.update(fields)
    with tenant_context(institute):
        return create_teacher(institute, **values)


def _pairs(teacher) -> set:
    # unscoped: test assertion outside a tenant context.
    links = TeacherBatchSubject.unscoped.filter(teacher=teacher)
    return {(link.batch.name, link.subject.name) for link in links}


@pytest.mark.parametrize(
    ("full_name", "expected"),
    [
        ("Sam", ("Sam", "")),
        ("Sam Sample", ("Sam", "Sample")),
        ("  Sam   Ali  Sample ", ("Sam", "Ali Sample")),
    ],
)
def test_split_full_name(full_name, expected) -> None:
    assert split_full_name(full_name) == expected


@pytest.mark.django_db
def test_create_teacher_makes_account_profile_and_links(school) -> None:
    teacher = _create(school, cnic="3520200000001", address=" Street 1 ")

    user = teacher.user
    assert user.role == Role.TEACHER
    assert user.email == "new.teacher@example.com"
    assert (user.first_name, user.last_name) == ("Sam", "Ali Sample")
    assert user.phone == "0300-2222222"
    assert user.is_active is True
    assert authenticate(username=user.email, password=TEST_LOGIN_PASSWORD) == user
    assert teacher.teacher_code == "TCH-004"  # the school fixture made three
    assert (teacher.cnic, teacher.address) == ("3520200000001", "Street 1")
    assert _pairs(teacher) == {("Morning", "Math"), ("Morning", "Physics")}


@pytest.mark.django_db
@pytest.mark.parametrize("email", ["t1-a@example.com", "T1-B@EXAMPLE.COM"])
def test_create_rejects_any_used_email(school, email) -> None:
    with pytest.raises(ValidationError) as error:
        _create(school, email=email)

    assert error.value.message_dict == {"email": [EMAIL_TAKEN]}


@pytest.mark.django_db
def test_create_rejects_weak_password_and_saves_nothing(school) -> None:
    with pytest.raises(ValidationError) as error:
        _create(school, password=TEST_INVALID_PASSWORD_FOR_VALIDATION)

    assert "password" in error.value.message_dict
    assert not User.objects.filter(email="new.teacher@example.com").exists()


@pytest.mark.django_db
def test_create_without_pairs_saves_nothing(school) -> None:
    with pytest.raises(ValidationError) as error:
        _create(school, selections={})

    assert error.value.message_dict == {
        "batch_subjects": ["Choose at least one batch."]
    }
    assert not User.objects.filter(email="new.teacher@example.com").exists()


@pytest.mark.django_db
def test_create_needs_tenant_context(school) -> None:
    with pytest.raises(TenantContextError):
        create_teacher(
            school.morning.institute,
            full_name="Sam",
            email="x@example.com",
            password=TEST_LOGIN_PASSWORD,
            phone="1",
            selections={school.morning: [school.math]},
        )


@pytest.mark.django_db
def test_update_teacher_changes_fields_and_pairs(school) -> None:
    teacher = school.teacher_1
    with tenant_context(teacher.institute):
        update_teacher(
            teacher,
            full_name="Robin Example",
            email="Robin@Example.com",
            phone="0311-0000000",
            joining_date=None,
            selections={school.evening: [school.physics]},
        )

    user = User.objects.get(pk=teacher.user_id)
    assert (user.first_name, user.last_name) == ("Robin", "Example")
    assert user.email == "robin@example.com"
    assert _pairs(teacher) == {("Evening", "Physics")}


@pytest.mark.django_db
def test_update_keeps_own_email_but_rejects_another(school) -> None:
    teacher = school.teacher_1
    common = {
        "full_name": "Sam",
        "phone": "1",
        "selections": {school.morning: [school.math]},
    }
    with tenant_context(teacher.institute):
        update_teacher(teacher, email="T1-A@example.com", **common)
        with pytest.raises(ValidationError) as error:
            update_teacher(teacher, email="t2-a@example.com", **common)

    assert error.value.message_dict == {"email": [EMAIL_TAKEN]}
    assert User.objects.get(pk=teacher.user_id).email == "t1-a@example.com"


@pytest.mark.django_db
def test_deactivate_blocks_sign_in_and_activate_restores(school) -> None:
    teacher = school.teacher_1
    email = teacher.user.email
    with tenant_context(teacher.institute):
        set_teacher_active(teacher, is_active=False)

    teacher.refresh_from_db()
    assert teacher.status == "inactive"
    assert User.objects.get(pk=teacher.user_id).is_active is False
    assert authenticate(username=email, password=TEST_LOGIN_PASSWORD) is None

    with tenant_context(teacher.institute):
        set_teacher_active(teacher, is_active=True)

    teacher.refresh_from_db()
    assert teacher.status == "active"
    assert authenticate(username=email, password=TEST_LOGIN_PASSWORD) is not None


@pytest.mark.django_db
def test_status_needs_tenant_context(school) -> None:
    with pytest.raises(TenantContextError):
        set_teacher_active(school.teacher_1, is_active=False)


@pytest.mark.django_db
def test_other_users_keep_their_email_case(institute_a) -> None:
    make_user(email="keep@example.com", role=Role.STUDENT, institute=institute_a)

    assert User.objects.filter(email="keep@example.com").exists()
