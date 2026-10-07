"""Setting a person's (batch, subject) pairs (roadmap 2.3, SPEC 4.1 and 4.2)."""

from __future__ import annotations

import pytest
from apps.academics.models import (
    Batch,
    StudentBatchSubject,
    Subject,
    TeacherBatchSubject,
)
from apps.academics.services import (
    create_name_row,
    rename_name_row,
    set_name_row_active,
    set_student_batch_subjects,
)
from apps.core.tenancy import TenantContextError, tenant_context
from django.core.exceptions import ValidationError

from tests.academics.conftest import link_student, link_teacher, make_lists


def _pairs(links) -> set:
    return {(link.batch.name, link.subject.name) for link in links}


def _student_pairs(profile) -> set:
    # unscoped: test assertion outside a tenant context.
    return _pairs(StudentBatchSubject.unscoped.filter(student=profile))


def _teacher_pairs(profile) -> set:
    # unscoped: test assertion outside a tenant context.
    return _pairs(TeacherBatchSubject.unscoped.filter(teacher=profile))


@pytest.mark.django_db
def test_student_pairs_are_created(school) -> None:
    assert _student_pairs(school.student_1) == {
        ("Morning", "Math"),
        ("Morning", "Physics"),
    }


@pytest.mark.django_db
def test_teacher_pairs_are_created(school) -> None:
    assert _teacher_pairs(school.teacher_1) == {("Morning", "Math")}


@pytest.mark.django_db
def test_setting_pairs_replaces_old_ones(school) -> None:
    link_student(
        school.student_1,
        {school.morning: [school.math], school.evening: [school.physics]},
    )

    assert _student_pairs(school.student_1) == {
        ("Morning", "Math"),
        ("Evening", "Physics"),
    }


@pytest.mark.django_db
def test_setting_the_same_pairs_changes_nothing(school) -> None:
    # unscoped: test assertion outside a tenant context.
    before = set(
        StudentBatchSubject.unscoped.filter(student=school.student_1).values_list(
            "pk", flat=True
        )
    )
    link_student(school.student_1, {school.morning: [school.physics, school.math]})

    # unscoped: test assertion outside a tenant context.
    after = set(
        StudentBatchSubject.unscoped.filter(student=school.student_1).values_list(
            "pk", flat=True
        )
    )
    assert after == before


@pytest.mark.django_db
def test_other_people_keep_their_pairs(school) -> None:
    link_student(school.student_1, {school.evening: [school.physics]})

    assert _student_pairs(school.student_2) == {("Evening", "Physics")}


@pytest.mark.django_db
def test_at_least_one_batch_is_required(school) -> None:
    with pytest.raises(ValidationError) as error:
        link_student(school.student_1, {})

    assert error.value.message_dict == {"batches": ["Choose at least one batch."]}


@pytest.mark.django_db
def test_each_batch_needs_a_subject(school) -> None:
    with pytest.raises(ValidationError) as error:
        link_teacher(
            school.teacher_1, {school.morning: [school.math], school.evening: []}
        )

    assert error.value.message_dict == {
        "subjects": ["Choose at least one subject for Evening."]
    }
    assert _teacher_pairs(school.teacher_1) == {("Morning", "Math")}


@pytest.mark.django_db
def test_batch_from_other_institute_is_rejected(school) -> None:
    with pytest.raises(ValidationError) as error:
        link_student(school.student_1, {school.batch_b: [school.math]})

    assert error.value.messages == ["Choose a batch and subject from this institute."]
    assert len(_student_pairs(school.student_1)) == 2


@pytest.mark.django_db
def test_subject_from_other_institute_is_rejected(school, institute_b) -> None:
    (chemistry_b,) = make_lists(institute_b, Subject, "Chemistry")

    with pytest.raises(ValidationError):
        link_student(school.student_1, {school.morning: [chemistry_b]})


@pytest.mark.django_db
def test_inactive_batch_cannot_be_added(school) -> None:
    # unscoped: test setup outside a tenant context.
    Batch.unscoped.filter(pk=school.evening.pk).update(is_active=False)
    school.evening.refresh_from_db()

    with pytest.raises(ValidationError) as error:
        link_student(school.student_1, {school.evening: [school.physics]})

    assert error.value.messages == ["Evening is inactive and cannot be added."]


@pytest.mark.django_db
def test_inactive_subject_cannot_be_added(school) -> None:
    (chemistry,) = make_lists(school.morning.institute, Subject, "Chemistry")
    # unscoped: test setup outside a tenant context.
    Subject.unscoped.filter(pk=chemistry.pk).update(is_active=False)
    chemistry.refresh_from_db()

    with pytest.raises(ValidationError) as error:
        link_student(school.student_1, {school.morning: [chemistry]})

    assert error.value.messages == ["Chemistry is inactive and cannot be added."]


@pytest.mark.django_db
def test_inactive_pair_that_is_already_linked_may_stay(school) -> None:
    # unscoped: test setup outside a tenant context.
    Batch.unscoped.filter(pk=school.morning.pk).update(is_active=False)
    school.morning.refresh_from_db()

    link_student(school.student_1, {school.morning: [school.math]})

    assert _student_pairs(school.student_1) == {("Morning", "Math")}


@pytest.mark.django_db
def test_setting_pairs_needs_tenant_context(school) -> None:
    with pytest.raises(TenantContextError):
        set_student_batch_subjects(school.student_1, {school.morning: [school.math]})


@pytest.mark.django_db
def test_setting_pairs_rejects_other_institute_context(school, institute_b) -> None:
    with tenant_context(institute_b), pytest.raises(TenantContextError):
        set_student_batch_subjects(school.student_1, {school.morning: [school.math]})


@pytest.mark.django_db
def test_list_row_services_need_tenant_context(institute_a) -> None:
    (row,) = make_lists(institute_a, Batch, "Morning")

    with pytest.raises(TenantContextError):
        create_name_row(Batch, institute_a, name="Evening", noun="batch")
    with pytest.raises(TenantContextError):
        rename_name_row(row, name="Late", noun="batch")
    with pytest.raises(TenantContextError):
        set_name_row_active(row, is_active=False)
