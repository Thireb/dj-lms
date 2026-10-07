"""Link students and teachers to (batch, subject) pairs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.academics.models import (
    Batch,
    StudentBatchSubject,
    Subject,
    TeacherBatchSubject,
)
from apps.core.tenancy import require_tenant_context
from apps.institutes.models import Institute
from apps.people.models import StudentProfile, TeacherProfile

Selections = Mapping[Batch, Iterable[Subject]]
Pair = tuple[int, int]


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
