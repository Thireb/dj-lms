"""Publish, submit and grade assignments (roadmap 5.1, SPEC 4.16 and 6.8),
and keep the teacher's question bank (roadmap 5.2).

A student is expected to answer an assignment when an enrolment of theirs
has the assignment's batch and subject and was made before the due time.
A student who already answered is expected too, so an answer stays listed
after the enrolment is removed. An inactive student (one who left) is
expected only where they answered.

Answers are taken until the due time; after it, a student with no answer
has "Missed" (SPEC 6.8 allows late answers for homework only).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.academics.models import (
    Batch,
    StudentBatchSubject,
    Subject,
    TeacherBatchSubject,
)
from apps.assessments.models import (
    MAX_OPTIONS,
    MIN_OPTIONS,
    Assignment,
    Question,
    QuestionKind,
    QuestionOption,
    Submission,
    SubmissionStatus,
)
from apps.institutes.models import Institute
from apps.people.models import ProfileStatus, StudentProfile, TeacherProfile

CLOSED_MESSAGE = "The due time has passed. Answers are no longer taken."


@dataclass(frozen=True)
class AssignmentDetails:
    title: str
    instructions: str
    teacher: TeacherProfile
    batch: Batch
    subject: Subject
    total_marks: int
    due_at: datetime


def is_open(assignment: Assignment, now: datetime | None = None) -> bool:
    return (now or timezone.now()) < assignment.due_at


def submission_status(
    assignment: Assignment, submission: Submission | None, now: datetime
) -> str:
    """SPEC 2: pending, submitted, graded or missed (see the module text)."""
    if submission is None:
        if is_open(assignment, now):
            return SubmissionStatus.PENDING
        return SubmissionStatus.MISSED
    if submission.is_graded:
        return SubmissionStatus.GRADED
    return SubmissionStatus.SUBMITTED


# Publish


def _check(
    institute: Institute,
    details: AssignmentDetails,
    old: Assignment | None,
    now: datetime,
) -> None:
    errors: dict[str, list[str]] = defaultdict(list)
    for name in ("teacher", "batch", "subject"):
        if getattr(details, name).institute_id != institute.pk:
            errors[name].append("Must belong to this institute.")
    if errors:
        raise ValidationError(errors)
    pair = (details.batch.pk, details.subject.pk)
    kept = old is not None and (old.batch_id, old.subject_id) == pair
    if not kept:
        linked = TeacherBatchSubject.objects.filter(
            teacher=details.teacher, batch=details.batch, subject=details.subject
        ).exists()
        if not linked:
            errors["subject"].append("The teacher does not teach this subject.")
        elif not (details.batch.is_active and details.subject.is_active):
            errors["subject"].append("This batch or subject is inactive.")
        if old is not None and old.submissions.exists():
            errors["subject"].append(
                "Students have answered, so the batch and subject stay the same."
            )
    if (old is None or details.due_at != old.due_at) and details.due_at <= now:
        errors["due_at"].append("Choose a due time in the future.")
    if old is not None:
        top = max(
            (row.marks for row in old.submissions.all() if row.marks is not None),
            default=None,
        )
        if top is not None and details.total_marks < top:
            errors["total_marks"].append(
                f"A student already has {_marks_text(top)} marks. "
                "Total marks cannot be less."
            )
    if errors:
        raise ValidationError(dict(errors))


def _apply(assignment: Assignment, details: AssignmentDetails) -> Assignment:
    for name in (
        "title",
        "instructions",
        "teacher",
        "batch",
        "subject",
        "total_marks",
        "due_at",
    ):
        setattr(assignment, name, getattr(details, name))
    assignment.save()
    return assignment


def create_assignment(
    institute: Institute, details: AssignmentDetails, *, now: datetime | None = None
) -> Assignment:
    _check(institute, details, None, now or timezone.now())
    return _apply(Assignment(institute=institute), details)


def update_assignment(
    assignment: Assignment,
    details: AssignmentDetails,
    *,
    now: datetime | None = None,
) -> Assignment:
    """The teacher stays the same. The row is locked, so a grade saved at
    the same time cannot pass the total marks check."""
    with transaction.atomic():
        locked = Assignment.objects.select_for_update().get(pk=assignment.pk)
        if details.teacher.pk != locked.teacher_id:
            raise ValidationError({"teacher": "The teacher cannot change."})
        _check(locked.institute, details, locked, now or timezone.now())
        return _apply(locked, details)


# Who answers


def _expected_ids(assignment: Assignment) -> set[int]:
    enrolled = StudentBatchSubject.objects.filter(
        batch_id=assignment.batch_id,
        subject_id=assignment.subject_id,
        created_at__lt=assignment.due_at,
        student__status=ProfileStatus.ACTIVE,
    ).values_list("student_id", flat=True)
    answered = Submission.objects.filter(assignment=assignment).values_list(
        "student_id", flat=True
    )
    return set(enrolled) | set(answered)


def is_expected(assignment: Assignment, student: StudentProfile) -> bool:
    return student.pk in _expected_ids(assignment)


@dataclass(frozen=True)
class SubmissionRow:
    student: StudentProfile
    submission: Submission | None
    status: str


def submission_rows(
    assignment: Assignment, *, now: datetime | None = None
) -> list[SubmissionRow]:
    """The expected students by name, with their answers (teacher page)."""
    now = now or timezone.now()
    answers = {
        row.student_id: row for row in Submission.objects.filter(assignment=assignment)
    }
    students = (
        StudentProfile.objects.filter(pk__in=_expected_ids(assignment))
        .select_related("user")
        .order_by("user__first_name", "user__last_name", "pk")
    )
    rows = []
    for student in students:
        answer = answers.get(student.pk)
        rows.append(
            SubmissionRow(student, answer, submission_status(assignment, answer, now))
        )
    return rows


@dataclass(frozen=True)
class AssignmentCount:
    submitted: int  # answered, graded or not
    graded: int
    total: int  # expected students

    @property
    def to_grade(self) -> int:
        return self.submitted - self.graded


def assignment_counts(assignments: list[Assignment]) -> dict[int, AssignmentCount]:
    """Submitted / Total for a page of assignments, in 2 queries."""
    if not assignments:
        return {}
    links = StudentBatchSubject.objects.filter(
        batch_id__in={row.batch_id for row in assignments},
        student__status=ProfileStatus.ACTIVE,
    ).values_list("student_id", "batch_id", "subject_id", "created_at")
    links = list(links)
    answers: dict[int, dict[int, bool]] = defaultdict(dict)
    rows = Submission.objects.filter(assignment__in=assignments).values_list(
        "assignment_id", "student_id", "marks"
    )
    for assignment_id, student_id, marks in rows:
        answers[assignment_id][student_id] = marks is not None
    counts = {}
    for assignment in assignments:
        own = answers[assignment.pk]
        expected = {
            student_id
            for student_id, batch_id, subject_id, created_at in links
            if batch_id == assignment.batch_id
            and subject_id == assignment.subject_id
            and created_at < assignment.due_at
        }
        counts[assignment.pk] = AssignmentCount(
            submitted=len(own),
            graded=sum(own.values()),
            total=len(expected | set(own)),
        )
    return counts


def answers_to_grade(user: Any) -> int:
    """Answers to the viewer's assignments with no marks yet (teacher
    dashboard, SPEC 8 "pending reviews")."""
    return Submission.objects.for_user(user).filter(marks__isnull=True).count()


# Student side


@dataclass(frozen=True)
class StudentAssignment:
    assignment: Assignment
    submission: Submission | None
    status: str


def student_assignments(
    student: StudentProfile,
    *,
    subject_id: int | None = None,
    status: str = "",
    now: datetime | None = None,
) -> list[StudentAssignment]:
    """The assignments a student is expected to answer, the next due first
    and then the newest past ones. The caller checks that the viewer may
    see the student."""
    now = now or timezone.now()
    links = list(
        StudentBatchSubject.objects.filter(
            student=student, student__status=ProfileStatus.ACTIVE
        ).values_list("batch_id", "subject_id", "created_at")
    )
    answers = {
        row.assignment_id: row for row in Submission.objects.filter(student=student)
    }
    enrolled = Q(pk__in=answers)
    for batch_id, link_subject_id, created_at in links:
        enrolled |= Q(
            batch_id=batch_id, subject_id=link_subject_id, due_at__gt=created_at
        )
    assignments = Assignment.objects.filter(enrolled).select_related(
        "subject", "teacher__user", "batch"
    )
    if subject_id is not None:
        assignments = assignments.filter(subject_id=subject_id)
    rows = []
    for assignment in assignments:
        answer = answers.get(assignment.pk)
        rows.append(
            StudentAssignment(
                assignment, answer, submission_status(assignment, answer, now)
            )
        )
    if status:
        rows = [row for row in rows if row.status == status]
    upcoming = sorted(
        (row for row in rows if row.assignment.due_at > now),
        key=lambda row: (row.assignment.due_at, row.assignment.pk),
    )
    past = sorted(
        (row for row in rows if row.assignment.due_at <= now),
        key=lambda row: (row.assignment.due_at, row.assignment.pk),
        reverse=True,
    )
    return upcoming + past


def submit_answer(
    assignment: Assignment,
    student: StudentProfile,
    answer: str,
    *,
    now: datetime | None = None,
) -> Submission:
    """Save or replace a student's answer until the due time. A graded
    answer stays as the teacher graded it."""
    with transaction.atomic():
        locked = Assignment.objects.select_for_update().get(pk=assignment.pk)
        if not is_open(locked, now):
            raise ValidationError(CLOSED_MESSAGE)
        if not is_expected(locked, student):
            raise ValidationError("This assignment is not for this student.")
        if not answer.strip():
            raise ValidationError({"answer": "Write your answer."})
        row = Submission.objects.filter(assignment=locked, student=student).first()
        if row is not None and row.is_graded:
            raise ValidationError("This answer is graded and cannot change.")
        if row is None:
            row = Submission(institute=locked.institute, assignment=locked)
            row.student = student
        row.answer = answer
        row.submitted_at = now or timezone.now()
        row.save()
        return row


# Grade


def grade_submission(
    submission: Submission,
    marks: Decimal,
    feedback: str,
    *,
    graded_by: Any,
    now: datetime | None = None,
) -> Submission:
    """Save or change the marks and feedback of one answer."""
    with transaction.atomic():
        assignment = Assignment.objects.select_for_update().get(
            pk=submission.assignment_id
        )
        row = Submission.objects.select_for_update().get(pk=submission.pk)
        if marks < 0 or marks > assignment.total_marks:
            raise ValidationError(
                {"marks": f"Give 0 to {assignment.total_marks} marks."}
            )
        row.marks = marks
        row.feedback = feedback
        row.graded_at = now or timezone.now()
        row.graded_by = graded_by
        row.save()
        return row


def _marks_text(marks: Decimal) -> str:
    """Example: 7, 7.5."""
    return f"{marks:.1f}".removesuffix(".0")


def marks_text(marks: Decimal | None, total: int) -> str:
    """Example: 7.5 / 10; a dash before grading."""
    if marks is None:
        return "-"
    return f"{_marks_text(marks)} / {total}"


# Question bank (roadmap 5.2, SPEC 4.16)
#
# Each teacher has their own bank. A question has one of the teacher's
# subjects (any of their batches). An MCQ question has 2 to 6 options and
# exactly one correct; a short answer question has no options.


@dataclass(frozen=True)
class QuestionDetails:
    teacher: TeacherProfile
    subject: Subject
    kind: str
    text: str
    marks: int
    explanation: str = ""
    options: tuple[str, ...] = ()
    correct: int | None = None  # index into options


def _check_question(
    institute: Institute, details: QuestionDetails, old: Question | None
) -> None:
    errors: dict[str, list[str]] = defaultdict(list)
    for name in ("teacher", "subject"):
        if getattr(details, name).institute_id != institute.pk:
            errors[name].append("Must belong to this institute.")
    if errors:
        raise ValidationError(dict(errors))
    if old is None or old.subject_id != details.subject.pk:
        taught = TeacherBatchSubject.objects.filter(
            teacher=details.teacher, subject=details.subject
        ).exists()
        if not taught:
            errors["subject"].append("The teacher does not teach this subject.")
        elif not details.subject.is_active:
            errors["subject"].append("This subject is inactive.")
    if not details.text.strip():
        errors["text"].append("Write the question.")
    if details.kind == QuestionKind.MCQ:
        _check_options(details, errors)
    elif details.kind == QuestionKind.SHORT:
        if details.options:
            errors["options"].append("A short answer question has no options.")
    else:
        errors["kind"].append("Choose MCQ or Short answer.")
    if errors:
        raise ValidationError(dict(errors))


def _check_options(details: QuestionDetails, errors: dict[str, list[str]]) -> None:
    options = details.options
    if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
        errors["options"].append(
            f"Give {MIN_OPTIONS} to {MAX_OPTIONS} options for an MCQ question."
        )
    elif any(not option.strip() for option in options):
        errors["options"].append("An option is empty.")
    elif len({option.strip().casefold() for option in options}) < len(options):
        errors["options"].append("Two options are the same.")
    if details.correct is None or not 0 <= details.correct < len(options):
        errors["correct"].append("Choose the correct option.")


def save_question(
    institute: Institute,
    details: QuestionDetails,
    question: Question | None = None,
) -> Question:
    """Add a question, or replace one (its options too). The teacher stays
    the same."""
    if question is not None and details.teacher.pk != question.teacher_id:
        raise ValidationError({"teacher": "The teacher cannot change."})
    _check_question(institute, details, question)
    with transaction.atomic():
        row = question or Question(institute=institute, teacher=details.teacher)
        row.subject = details.subject
        row.kind = details.kind
        row.text = details.text
        row.marks = details.marks
        row.explanation = details.explanation
        row.save()
        QuestionOption.objects.filter(question=row).delete()
        for position, text in enumerate(details.options, start=1):
            QuestionOption.objects.create(
                institute=institute,
                question=row,
                position=position,
                text=text.strip(),
                is_correct=position - 1 == details.correct,
            )
    return row


def delete_question(question: Question) -> None:
    question.delete()


def list_questions(
    user: Any,
    *,
    subject_id: int | None = None,
    kind: str = "",
    search: str = "",
) -> Any:
    """The viewer's questions, the newest change first, with their subject
    and options (2 queries for a page)."""
    rows = (
        Question.objects.for_user(user)
        .select_related("subject")
        .prefetch_related("options")
    )
    if subject_id is not None:
        rows = rows.filter(subject_id=subject_id)
    if kind:
        rows = rows.filter(kind=kind)
    if search:
        rows = rows.filter(text__icontains=search)
    return rows


def correct_option(question: Question) -> QuestionOption | None:
    """The correct option of an MCQ question (uses the prefetched options)."""
    return next((row for row in question.options.all() if row.is_correct), None)
