"""Profile creation, ID codes and model checks (roadmap 2.1)."""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.people.models import CodeSequence, StudentProfile, TeacherProfile
from apps.people.services import (
    TenantContextError,
    create_guardian_profile,
    create_student_profile,
    create_teacher_profile,
    next_code,
)
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from tests.conftest import make_user
from tests.people.conftest import guardian, student, teacher


@pytest.mark.django_db
def test_student_codes_count_up_per_institute(institute_a, institute_b) -> None:
    first = student(institute_a, "s1-a@example.com")
    second = student(institute_a, "s2-a@example.com")
    other = student(institute_b, "s1-b@example.com")

    assert first.student_code == "STU-001"
    assert second.student_code == "STU-002"
    assert other.student_code == "STU-001"


@pytest.mark.django_db
def test_teacher_codes_use_their_own_sequence(institute_a) -> None:
    student(institute_a, "s1-a@example.com")
    first = teacher(institute_a, "t1-a@example.com")
    second = teacher(institute_a, "t2-a@example.com")

    assert first.teacher_code == "TCH-001"
    assert second.teacher_code == "TCH-002"


@pytest.mark.django_db
def test_code_of_a_removed_student_is_not_reused(institute_a) -> None:
    student(institute_a, "s1-a@example.com")
    removed = student(institute_a, "s2-a@example.com")
    user = removed.user
    # unscoped: test cleanup of a row outside any tenant context.
    StudentProfile.unscoped.filter(pk=removed.pk).delete()
    user.delete()

    assert student(institute_a, "s3-a@example.com").student_code == "STU-003"


@pytest.mark.django_db
def test_code_numbers_go_past_three_digits(institute_a) -> None:
    # unscoped: test setup of the counter row.
    CodeSequence.unscoped.create(institute=institute_a, prefix="STU", last_number=999)

    assert student(institute_a, "s1-a@example.com").student_code == "STU-1000"


@pytest.mark.django_db
def test_failed_create_does_not_use_a_number(institute_a) -> None:
    wrong_role = make_user(
        email="t-a@example.com", role=Role.TEACHER, institute=institute_a
    )
    with tenant_context(institute_a), pytest.raises(ValidationError):
        create_student_profile(wrong_role, guardian_phone="0300-0000000")

    assert student(institute_a, "s1-a@example.com").student_code == "STU-001"


@pytest.mark.django_db
def test_profile_rejects_user_with_wrong_role(institute_a) -> None:
    user = make_user(email="g-a@example.com", role=Role.GUARDIAN, institute=institute_a)
    with tenant_context(institute_a), pytest.raises(ValidationError) as error:
        create_teacher_profile(user)

    assert "teacher role" in str(error.value)


@pytest.mark.django_db
def test_profile_rejects_user_from_other_institute(institute_a, institute_b) -> None:
    user = make_user(email="t-b@example.com", role=Role.TEACHER, institute=institute_b)
    with pytest.raises(ValidationError) as error:
        TeacherProfile(institute=institute_a, user=user, teacher_code="TCH-900").save()

    assert "same institute" in str(error.value)


@pytest.mark.django_db
def test_cnic_must_be_13_digits(institute_a) -> None:
    user = make_user(email="s-a@example.com", role=Role.STUDENT, institute=institute_a)
    with tenant_context(institute_a), pytest.raises(ValidationError) as error:
        create_student_profile(user, guardian_phone="0300-0000000", cnic="12345")

    assert "13 digits" in str(error.value)


@pytest.mark.django_db
def test_valid_cnic_is_saved(institute_a) -> None:
    user = make_user(email="s-a@example.com", role=Role.STUDENT, institute=institute_a)
    with tenant_context(institute_a):
        profile = create_student_profile(
            user, guardian_phone="0300-0000000", cnic="3520200000001"
        )

    assert profile.cnic == "3520200000001"


@pytest.mark.django_db
def test_guardian_phone_is_required(institute_a) -> None:
    user = make_user(email="s-a@example.com", role=Role.STUDENT, institute=institute_a)
    with tenant_context(institute_a), pytest.raises(ValidationError) as error:
        create_student_profile(user)

    assert "guardian_phone" in error.value.message_dict


@pytest.mark.django_db
def test_student_code_is_unique_per_institute(institute_a) -> None:
    existing = student(institute_a, "s1-a@example.com")
    user = make_user(email="s2-a@example.com", role=Role.STUDENT, institute=institute_a)
    with pytest.raises(IntegrityError), transaction.atomic():
        StudentProfile(
            institute=institute_a,
            user=user,
            student_code=existing.student_code,
            guardian_phone="0300-0000000",
        ).save()


@pytest.mark.django_db
def test_one_profile_per_user(institute_a) -> None:
    existing = student(institute_a, "s1-a@example.com")
    with pytest.raises(IntegrityError), transaction.atomic():
        StudentProfile(
            institute=institute_a,
            user=existing.user,
            student_code="STU-900",
            guardian_phone="0300-0000000",
        ).save()


@pytest.mark.django_db
def test_new_profiles_are_active(institute_a) -> None:
    assert student(institute_a, "s1-a@example.com").status == "active"
    assert teacher(institute_a, "t1-a@example.com").status == "active"


@pytest.mark.django_db
def test_guardian_profile_is_created(institute_a) -> None:
    profile = guardian(institute_a, "g1-a@example.com")

    assert profile.institute == institute_a
    assert profile.user.guardian_profile == profile


@pytest.mark.django_db
def test_next_code_needs_tenant_context(institute_a) -> None:
    with pytest.raises(TenantContextError):
        next_code(institute_a, "STU")


@pytest.mark.django_db
def test_next_code_rejects_other_institute_context(institute_a, institute_b) -> None:
    with tenant_context(institute_b), pytest.raises(TenantContextError):
        next_code(institute_a, "STU")


@pytest.mark.django_db
def test_create_needs_tenant_context(institute_a) -> None:
    user = make_user(email="g-a@example.com", role=Role.GUARDIAN, institute=institute_a)
    with pytest.raises(TenantContextError):
        create_guardian_profile(user)


@pytest.mark.django_db
def test_teacher_cnic_must_be_13_digits(institute_a) -> None:
    user = make_user(email="t-a@example.com", role=Role.TEACHER, institute=institute_a)
    with tenant_context(institute_a), pytest.raises(ValidationError) as error:
        create_teacher_profile(user, cnic="35202-0000000-1")

    assert "13 digits" in str(error.value)
