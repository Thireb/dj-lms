"""Academics models: names, links and tenant isolation (roadmap 2.3)."""

from __future__ import annotations

import pytest
from apps.academics.models import (
    Batch,
    ClassLabel,
    StudentBatchSubject,
    Subject,
    TeacherBatchSubject,
)
from apps.core.roles import Role
from apps.core.tenancy import clear_current_institute, tenant_context
from apps.people.models import StudentProfile
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from tests.academics.conftest import make_lists
from tests.conftest import FakeUser
from tests.people.conftest import student, teacher

ALL_MODELS = [ClassLabel, Batch, Subject, StudentBatchSubject, TeacherBatchSubject]
NAME_LISTS = [ClassLabel, Batch, Subject]


@pytest.mark.django_db
@pytest.mark.parametrize("model", NAME_LISTS)
def test_name_is_unique_per_institute_ignoring_case(institute_a, model) -> None:
    make_lists(institute_a, model, "Morning")

    with pytest.raises(IntegrityError), transaction.atomic():
        make_lists(institute_a, model, "MORNING")


@pytest.mark.django_db
@pytest.mark.parametrize("model", NAME_LISTS)
def test_same_name_is_allowed_in_another_institute(
    institute_a, institute_b, model
) -> None:
    make_lists(institute_a, model, "Morning")
    (other,) = make_lists(institute_b, model, "Morning")

    assert other.institute == institute_b


@pytest.mark.django_db
@pytest.mark.parametrize("model", NAME_LISTS)
def test_new_list_rows_are_active(institute_a, model) -> None:
    (row,) = make_lists(institute_a, model, "Morning")

    assert row.is_active is True


@pytest.mark.django_db
def test_student_link_rejects_batch_from_other_institute(
    institute_a, institute_b
) -> None:
    profile = student(institute_a, "s1-a@example.com")
    (batch_b,) = make_lists(institute_b, Batch, "Morning")
    (math,) = make_lists(institute_a, Subject, "Math")

    with pytest.raises(ValidationError) as error:
        StudentBatchSubject(
            institute=institute_a, student=profile, batch=batch_b, subject=math
        ).save()

    assert "batch" in error.value.message_dict


@pytest.mark.django_db
def test_teacher_link_rejects_teacher_from_other_institute(
    institute_a, institute_b
) -> None:
    profile_b = teacher(institute_b, "t1-b@example.com")
    (batch,) = make_lists(institute_a, Batch, "Morning")
    (math,) = make_lists(institute_a, Subject, "Math")

    with pytest.raises(ValidationError) as error:
        TeacherBatchSubject(
            institute=institute_a, teacher=profile_b, batch=batch, subject=math
        ).save()

    assert "teacher" in error.value.message_dict


@pytest.mark.django_db
def test_link_rejects_subject_from_other_institute(institute_a, institute_b) -> None:
    profile = teacher(institute_a, "t1-a@example.com")
    (batch,) = make_lists(institute_a, Batch, "Morning")
    (math_b,) = make_lists(institute_b, Subject, "Math")

    with pytest.raises(ValidationError) as error:
        TeacherBatchSubject(
            institute=institute_a, teacher=profile, batch=batch, subject=math_b
        ).save()

    assert "subject" in error.value.message_dict


@pytest.mark.django_db
def test_link_triple_is_unique(school) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        StudentBatchSubject(
            institute=school.morning.institute,
            student=school.student_1,
            batch=school.morning,
            subject=school.math,
        ).save()


@pytest.mark.django_db
def test_class_label_is_saved_on_student(school) -> None:
    profile = school.student_1
    profile.class_label = school.grade_9
    profile.save()

    # unscoped: test assertion outside a tenant context.
    assert StudentProfile.unscoped.get(pk=profile.pk).class_label == school.grade_9


@pytest.mark.django_db
def test_class_label_from_other_institute_is_rejected(school, institute_b) -> None:
    (label_b,) = make_lists(institute_b, ClassLabel, "Grade 9")
    profile = school.student_1
    profile.class_label = label_b

    with pytest.raises(ValidationError) as error:
        profile.save()

    assert "class_label" in error.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize("model", ALL_MODELS)
def test_no_tenant_context_returns_nothing(school, model) -> None:
    clear_current_institute()

    assert list(model.objects.all()) == []


@pytest.mark.django_db
@pytest.mark.parametrize("model", ALL_MODELS)
def test_tenant_context_returns_only_that_institute(school, institute_b, model):
    with tenant_context(institute_b):
        rows = list(model.objects.all())

    assert {row.institute_id for row in rows} <= {institute_b.pk}


@pytest.mark.django_db
@pytest.mark.parametrize("model", ALL_MODELS)
def test_anonymous_sees_nothing(school, anonymous_user, model) -> None:
    assert list(model.objects.for_user(anonymous_user)) == []


@pytest.mark.django_db
@pytest.mark.parametrize("model", ALL_MODELS)
def test_user_without_institute_sees_nothing(school, model) -> None:
    user = FakeUser(role=Role.INSTITUTE_ADMIN)

    assert list(model.objects.for_user(user)) == []
