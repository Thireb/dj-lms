"""Guardian enrolment and guardian-student links (roadmap 2.2)."""

from __future__ import annotations

import pytest
from apps.accounts.models import User
from apps.core.roles import Role
from apps.core.tenancy import (
    TenantContextError,
    clear_current_institute,
    tenant_context,
)
from apps.people.models import GuardianProfile, GuardianStudentLink, StudentProfile
from apps.people.services import (
    GUARDIAN_EMAIL_TAKEN,
    enrol_guardian,
)
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from tests.conftest import (
    TEST_INVALID_PASSWORD_FOR_VALIDATION,
    TEST_LOGIN_PASSWORD,
    TEST_NEW_PASSWORD,
    FakeUser,
    make_user,
)
from tests.people.conftest import account, guardian, student, teacher


def _enrol(profile: StudentProfile, email: str, **fields):
    fields.setdefault("password", TEST_LOGIN_PASSWORD)
    with tenant_context(profile.institute):
        return enrol_guardian(profile, email=email, **fields)


@pytest.fixture
def family(institute_a, institute_b) -> dict:
    """Guardian 1 has two children; guardian 2 has one; B has its own."""
    child_1 = student(institute_a, "c1-a@example.com")
    child_2 = student(institute_a, "c2-a@example.com")
    child_3 = student(institute_a, "c3-a@example.com")
    child_b = student(institute_b, "c1-b@example.com")
    parent_1 = _enrol(child_1, "p1-a@example.com").guardian
    _enrol(child_2, "p1-a@example.com")
    parent_2 = _enrol(child_3, "p2-a@example.com").guardian
    parent_b = _enrol(child_b, "p1-b@example.com").guardian
    return {
        "child_1": child_1,
        "child_2": child_2,
        "child_3": child_3,
        "child_b": child_b,
        "parent_1": parent_1,
        "parent_2": parent_2,
        "parent_b": parent_b,
    }


def _visible(model, user) -> set:
    return set(model.objects.for_user(user))


# Enrolment


@pytest.mark.django_db
def test_new_guardian_account_is_created_and_linked(institute_a) -> None:
    child = student(institute_a, "c1-a@example.com")

    result = _enrol(
        child,
        "  Parent.One@Example.com ",
        first_name=" Sam ",
        last_name="Sample",
        phone="0300-1111111",
    )

    user = result.guardian.user
    assert result.created is True
    assert user.email == "parent.one@example.com"
    assert user.role == Role.GUARDIAN
    assert user.institute == institute_a
    assert user.get_full_name() == "Sam Sample"
    assert user.phone == "0300-1111111"
    assert user.check_password(TEST_LOGIN_PASSWORD)
    # unscoped: test assertion outside a tenant context.
    assert list(GuardianStudentLink.unscoped.values_list("guardian", "student")) == [
        (result.guardian.pk, child.pk)
    ]


@pytest.mark.django_db
def test_second_child_links_to_existing_guardian(institute_a) -> None:
    first = student(institute_a, "c1-a@example.com")
    second = student(institute_a, "c2-a@example.com")
    original = _enrol(first, "parent@example.com", first_name="Sam").guardian

    result = _enrol(
        second,
        "PARENT@example.com",
        password=TEST_NEW_PASSWORD,
        first_name="Changed",
    )

    user = User.objects.get(pk=original.user_id)
    assert result.created is False
    assert result.guardian == original
    assert user.first_name == "Sam"
    assert user.check_password(TEST_LOGIN_PASSWORD)
    assert User.objects.filter(email__iexact="parent@example.com").count() == 1


@pytest.mark.django_db
def test_enrolling_the_same_pair_twice_keeps_one_link(institute_a) -> None:
    child = student(institute_a, "c1-a@example.com")
    _enrol(child, "parent@example.com")
    _enrol(child, "parent@example.com")

    # unscoped: test assertion outside a tenant context.
    assert GuardianStudentLink.unscoped.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role", [Role.STUDENT, Role.TEACHER, Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]
)
def test_email_of_another_role_is_rejected(institute_a, role) -> None:
    child = student(institute_a, "c1-a@example.com")
    make_user(email="taken@example.com", role=role, institute=institute_a)

    with pytest.raises(ValidationError) as error:
        _enrol(child, "taken@example.com")

    assert error.value.message_dict == {"guardian_email": [GUARDIAN_EMAIL_TAKEN]}


@pytest.mark.django_db
def test_student_own_email_is_rejected(institute_a) -> None:
    child = student(institute_a, "c1-a@example.com")

    with pytest.raises(ValidationError) as error:
        _enrol(child, "c1-a@example.com")

    assert "guardian_email" in error.value.message_dict


@pytest.mark.django_db
def test_guardian_of_other_institute_is_rejected_without_leak(
    institute_a, institute_b
) -> None:
    child_a = student(institute_a, "c1-a@example.com")
    child_b = student(institute_b, "c1-b@example.com")
    _enrol(child_b, "parent@example.com")

    with pytest.raises(ValidationError) as error:
        _enrol(child_a, "parent@example.com")

    assert error.value.message_dict == {"guardian_email": [GUARDIAN_EMAIL_TAKEN]}
    # unscoped: test assertion outside a tenant context.
    assert not GuardianStudentLink.unscoped.filter(student=child_a).exists()


@pytest.mark.django_db
def test_super_admin_email_is_rejected(institute_a) -> None:
    child = student(institute_a, "c1-a@example.com")
    make_user(email="root@example.com", role=Role.SUPER_ADMIN)

    with pytest.raises(ValidationError):
        _enrol(child, "root@example.com")


@pytest.mark.django_db
def test_weak_password_creates_nothing(institute_a) -> None:
    child = student(institute_a, "c1-a@example.com")

    with pytest.raises(ValidationError) as error:
        _enrol(
            child,
            "parent@example.com",
            password=TEST_INVALID_PASSWORD_FOR_VALIDATION,
        )

    assert "guardian_password" in error.value.message_dict
    assert not User.objects.filter(email="parent@example.com").exists()


@pytest.mark.django_db
def test_existing_guardian_without_profile_gets_one(institute_a) -> None:
    child = student(institute_a, "c1-a@example.com")
    user = make_user(
        email="parent@example.com", role=Role.GUARDIAN, institute=institute_a
    )

    result = _enrol(child, "parent@example.com")

    assert result.created is False
    assert result.guardian.user == user


@pytest.mark.django_db
def test_enrol_needs_tenant_context(institute_a) -> None:
    child = student(institute_a, "c1-a@example.com")

    with pytest.raises(TenantContextError):
        enrol_guardian(child, email="parent@example.com", password=TEST_LOGIN_PASSWORD)
    assert not User.objects.filter(email="parent@example.com").exists()


@pytest.mark.django_db
def test_enrol_rejects_other_institute_context(institute_a, institute_b) -> None:
    child = student(institute_a, "c1-a@example.com")

    with tenant_context(institute_b), pytest.raises(TenantContextError):
        enrol_guardian(child, email="parent@example.com", password=TEST_LOGIN_PASSWORD)


# Link model


@pytest.mark.django_db
def test_link_rejects_guardian_from_other_institute(institute_a, institute_b) -> None:
    child = student(institute_a, "c1-a@example.com")
    parent_b = guardian(institute_b, "p-b@example.com")

    with pytest.raises(ValidationError) as error:
        GuardianStudentLink(
            institute=institute_a, guardian=parent_b, student=child
        ).save()

    assert "guardian" in error.value.message_dict


@pytest.mark.django_db
def test_link_rejects_student_from_other_institute(institute_a, institute_b) -> None:
    child_b = student(institute_b, "c1-b@example.com")
    parent = guardian(institute_a, "p-a@example.com")

    with pytest.raises(ValidationError) as error:
        GuardianStudentLink(
            institute=institute_a, guardian=parent, student=child_b
        ).save()

    assert "student" in error.value.message_dict


@pytest.mark.django_db
def test_link_pair_is_unique(institute_a) -> None:
    child = student(institute_a, "c1-a@example.com")
    parent = _enrol(child, "parent@example.com").guardian

    with pytest.raises(IntegrityError), transaction.atomic():
        GuardianStudentLink(
            institute=institute_a, guardian=parent, student=child
        ).save()


# Scopes


@pytest.mark.django_db
def test_guardian_sees_both_linked_children_only(family) -> None:
    user = family["parent_1"].user

    assert _visible(StudentProfile, user) == {family["child_1"], family["child_2"]}


@pytest.mark.django_db
def test_guardian_cannot_see_unlinked_student(family) -> None:
    user = family["parent_2"].user

    assert _visible(StudentProfile, user) == {family["child_3"]}


@pytest.mark.django_db
def test_guardian_still_sees_only_own_guardian_profile(family) -> None:
    user = family["parent_1"].user

    assert _visible(GuardianProfile, user) == {family["parent_1"]}


@pytest.mark.django_db
def test_student_sees_own_guardian_only(family) -> None:
    assert _visible(GuardianProfile, family["child_1"].user) == {family["parent_1"]}
    assert _visible(GuardianProfile, family["child_3"].user) == {family["parent_2"]}


@pytest.mark.django_db
def test_siblings_cannot_see_each_other(family) -> None:
    user = family["child_1"].user

    assert _visible(StudentProfile, user) == {family["child_1"]}


@pytest.mark.django_db
def test_guardian_link_does_not_cross_institutes(family, institute_a) -> None:
    # A guardian user moved to institute A keeps no reach into B.
    user = family["parent_b"].user
    user.institute = institute_a

    assert _visible(StudentProfile, user) == set()


@pytest.mark.django_db
def test_teacher_sees_no_guardians_or_links(family, institute_a) -> None:
    user = teacher(institute_a, "t1-a@example.com").user

    assert _visible(GuardianProfile, user) == set()
    assert _visible(GuardianStudentLink, user) == set()


@pytest.mark.django_db
def test_links_for_guardian_and_student(family) -> None:
    parent_links = _visible(GuardianStudentLink, family["parent_1"].user)
    child_links = _visible(GuardianStudentLink, family["child_2"].user)

    assert {link.student for link in parent_links} == {
        family["child_1"],
        family["child_2"],
    }
    assert {link.guardian for link in child_links} == {family["parent_1"]}
    assert len(child_links) == 1


@pytest.mark.django_db
@pytest.mark.parametrize("role", [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN])
def test_admins_see_institute_links(family, institute_a, role) -> None:
    user = account(institute_a, "admin-a@example.com", role)

    links = _visible(GuardianStudentLink, user)

    assert len(links) == 3
    assert {link.institute_id for link in links} == {institute_a.pk}


@pytest.mark.django_db
def test_super_admin_sees_all_links(family) -> None:
    user = account(None, "super@example.com", Role.SUPER_ADMIN)

    assert len(_visible(GuardianStudentLink, user)) == 4


@pytest.mark.django_db
def test_links_fail_closed(family, anonymous_user) -> None:
    clear_current_institute()

    assert list(GuardianStudentLink.objects.all()) == []
    assert _visible(GuardianStudentLink, anonymous_user) == set()
    assert _visible(GuardianStudentLink, FakeUser(role=Role.INSTITUTE_ADMIN)) == set()


@pytest.mark.django_db
def test_links_in_tenant_context_stay_in_institute(family, institute_b) -> None:
    with tenant_context(institute_b):
        links = list(GuardianStudentLink.objects.all())

    assert [link.student for link in links] == [family["child_b"]]
