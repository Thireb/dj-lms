"""Class, batch and subject lists, and the (batch, subject) links on people."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, QuerySet

from apps.academics.models import (
    Batch,
    ClassLabel,
    NameList,
    StudentBatchSubject,
    Subject,
    TeacherBatchSubject,
)
from apps.core.tenancy import require_tenant_context
from apps.institutes.models import Institute
from apps.people.models import StudentProfile, TeacherProfile

Selections = Mapping[Batch, Iterable[Subject]]
Pair = tuple[int, int]

# Relation from each list to the students on it, for the "Students" column.
STUDENT_RELATIONS = {
    ClassLabel: "students",
    Batch: "student_links__student",
    Subject: "student_links__student",
}


def list_name_rows(
    model: type[NameList], user: object, search: str = ""
) -> QuerySet[NameList]:
    """The user's rows, newest first, with ``student_count``."""
    rows = model.objects.for_user(user)
    if search:
        rows = rows.filter(name__icontains=search)
    relation = STUDENT_RELATIONS[model]
    return rows.annotate(student_count=Count(relation, distinct=True)).order_by(
        "-created_at", "-pk"
    )


def create_name_row(
    model: type[NameList], institute: Institute, *, name: str, noun: str
) -> NameList:
    require_tenant_context(institute)
    name = _clean_name(model, institute, name, noun)
    return model.objects.create(institute=institute, name=name)


def rename_name_row(row: NameList, *, name: str, noun: str) -> NameList:
    require_tenant_context(row.institute)
    row.name = _clean_name(type(row), row.institute, name, noun, exclude_pk=row.pk)
    row.save(update_fields=["name"])
    return row


def set_name_row_active(row: NameList, *, is_active: bool) -> NameList:
    require_tenant_context(row.institute)
    row.is_active = is_active
    row.save(update_fields=["is_active"])
    return row


def _clean_name(
    model: type[NameList],
    institute: Institute,
    name: str,
    noun: str,
    exclude_pk: int | None = None,
) -> str:
    name = " ".join(name.split())
    if not name:
        raise ValidationError({"name": "Enter a name."})
    taken = model.objects.filter(institute=institute, name__iexact=name)
    if exclude_pk is not None:
        taken = taken.exclude(pk=exclude_pk)
    if taken.exists():
        raise ValidationError({"name": f"A {noun} named {name} already exists."})
    return name


def set_student_batch_subjects(student: StudentProfile, selections: Selections) -> None:
    """Replace the student's (batch, subject) pairs with ``selections``."""
    _replace_pairs(StudentBatchSubject, "student", student, selections)


def set_teacher_batch_subjects(teacher: TeacherProfile, selections: Selections) -> None:
    """Replace the teacher's (batch, subject) pairs with ``selections``."""
    _replace_pairs(TeacherBatchSubject, "teacher", teacher, selections)


@transaction.atomic
def _replace_pairs(
    link_model: type[StudentBatchSubject] | type[TeacherBatchSubject],
    person_field: str,
    person: StudentProfile | TeacherProfile,
    selections: Selections,
) -> None:
    institute = person.institute
    require_tenant_context(institute)
    links = link_model.objects.filter(**{person_field: person})
    current = set(links.values_list("batch_id", "subject_id"))
    wanted = _validated_pairs(institute, selections, current)
    stale = current - wanted
    for batch_id, subject_id in stale:
        links.filter(batch_id=batch_id, subject_id=subject_id).delete()
    for batch_id, subject_id in sorted(wanted - current):
        link_model.objects.create(
            institute=institute,
            batch_id=batch_id,
            subject_id=subject_id,
            **{person_field: person},
        )


def _validated_pairs(
    institute: Institute, selections: Selections, current: set[Pair]
) -> set[Pair]:
    """Check the rules from SPEC 4.1 and 4.2 and return (batch, subject) ids.

    Inactive batches or subjects may stay if already linked, but cannot be
    added. Rows from another institute get the same message as unknown ones.
    """
    if not selections:
        raise ValidationError({"batches": "Choose at least one batch."})
    pairs: set[Pair] = set()
    for batch, subjects in selections.items():
        subjects = list(subjects)
        if not subjects:
            raise ValidationError(
                {"subjects": f"Choose at least one subject for {batch.name}."}
            )
        for item in (batch, *subjects):
            if item.institute_id != institute.pk:
                raise ValidationError("Choose a batch and subject from this institute.")
        for subject in subjects:
            pair = (batch.pk, subject.pk)
            if pair not in current:
                _check_active(batch, subject)
            pairs.add(pair)
    return pairs


def _check_active(batch: Batch, subject: Subject) -> None:
    for item in (batch, subject):
        if not item.is_active:
            raise ValidationError(f"{item.name} is inactive and cannot be added.")
