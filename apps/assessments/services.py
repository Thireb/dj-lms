"""Publish, submit and grade assignments (roadmap 5.1, SPEC 4.16 and 6.8),
keep the teacher's question bank (roadmap 5.2) and set up quizzes and exams
(roadmap 5.3).

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
from django.db.models import Count, Q, Sum
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
    Quiz,
    QuizKind,
    QuizQuestion,
    QuizStatus,
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
    if question is not None and question_in_opened_quiz(question):
        raise ValidationError(FIXED_MESSAGE)
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


IN_QUIZ_MESSAGE = (
    "This question is in a quiz. Remove it from the quiz first, or keep it."
)
FIXED_MESSAGE = (
    "This question is in a quiz that has opened, so it cannot change. "
    "Add a new question instead."
)


def delete_question(question: Question) -> None:
    """A question in a quiz stays in the bank (backlog AS6)."""
    if QuizQuestion.objects.filter(question=question).exists():
        raise ValidationError(IN_QUIZ_MESSAGE)
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


# Quizzes and exams: set-up (roadmap 5.3, SPEC 4.16 and 6.8)
#
# The teacher makes a quiz for one of their batches and subjects and adds
# questions of that subject from their bank. A draft is not seen by
# students. Publishing makes it "Scheduled"; it is "Live" from Opens until
# Opens + duration + 10 minutes, then "Closed". A quiz that has opened
# cannot change, and its questions cannot change or leave the bank.

OPENED_MESSAGE = "This quiz has opened, so it cannot change."


@dataclass(frozen=True)
class QuizDetails:
    title: str
    kind: str
    teacher: TeacherProfile
    batch: Batch
    subject: Subject
    opens_at: datetime
    duration_minutes: int
    pass_marks: int | None = None
    shuffle_questions: bool = False
    require_full_screen: bool = False
    flag_tab_leaving: bool = False


def quiz_status(quiz: Quiz, now: datetime | None = None) -> str:
    now = now or timezone.now()
    if not quiz.is_published:
        return QuizStatus.DRAFT
    if now < quiz.opens_at:
        return QuizStatus.SCHEDULED
    if now < quiz.closes_at:
        return QuizStatus.LIVE
    return QuizStatus.CLOSED


def has_opened(quiz: Quiz, now: datetime | None = None) -> bool:
    """A published quiz past its Opens time: its paper is fixed."""
    return quiz.is_published and (now or timezone.now()) >= quiz.opens_at


def quiz_total(quiz: Quiz) -> int:
    """Total marks: the sum of its questions' marks."""
    return sum(item.question.marks for item in quiz_items(quiz))


def quiz_items(quiz: Quiz) -> list[QuizQuestion]:
    return list(
        QuizQuestion.objects.filter(quiz=quiz)
        .select_related("question")
        .prefetch_related("question__options")
    )


def _check_quiz(
    institute: Institute, details: QuizDetails, old: Quiz | None, now: datetime
) -> None:
    errors: dict[str, list[str]] = defaultdict(list)
    for name in ("teacher", "batch", "subject"):
        if getattr(details, name).institute_id != institute.pk:
            errors[name].append("Must belong to this institute.")
    if errors:
        raise ValidationError(dict(errors))
    pair = (details.batch.pk, details.subject.pk)
    if old is None or (old.batch_id, old.subject_id) != pair:
        linked = TeacherBatchSubject.objects.filter(
            teacher=details.teacher, batch=details.batch, subject=details.subject
        ).exists()
        if not linked:
            errors["subject"].append("The teacher does not teach this subject.")
        elif not (details.batch.is_active and details.subject.is_active):
            errors["subject"].append("This batch or subject is inactive.")
    if old is not None and old.subject_id != details.subject.pk:
        if QuizQuestion.objects.filter(quiz=old).exists():
            errors["subject"].append(
                "Remove the questions first: they belong to the old subject."
            )
    if (old is None or details.opens_at != old.opens_at) and details.opens_at <= now:
        errors["opens_at"].append("Choose an opening time in the future.")
    if old is not None and details.pass_marks is not None:
        total = quiz_total(old)
        if total and details.pass_marks > total:
            errors["pass_marks"].append(
                f"Pass marks are more than the total ({total})."
            )
    if errors:
        raise ValidationError(dict(errors))


def _apply_quiz(quiz: Quiz, details: QuizDetails) -> Quiz:
    for name in (
        "title",
        "kind",
        "teacher",
        "batch",
        "subject",
        "opens_at",
        "duration_minutes",
        "pass_marks",
        "shuffle_questions",
    ):
        setattr(quiz, name, getattr(details, name))
    exam = details.kind == QuizKind.EXAM  # SPEC 4.16: exam settings only
    quiz.require_full_screen = exam and details.require_full_screen
    quiz.flag_tab_leaving = exam and details.flag_tab_leaving
    quiz.save()
    return quiz


def create_quiz(
    institute: Institute, details: QuizDetails, *, now: datetime | None = None
) -> Quiz:
    """A new quiz is a draft."""
    _check_quiz(institute, details, None, now or timezone.now())
    return _apply_quiz(Quiz(institute=institute), details)


def _locked_quiz(quiz: Quiz, now: datetime | None) -> Quiz:
    """Lock the quiz row; refuse once it has opened."""
    locked = Quiz.objects.select_for_update().get(pk=quiz.pk)
    if has_opened(locked, now):
        raise ValidationError(OPENED_MESSAGE)
    return locked


def update_quiz(
    quiz: Quiz, details: QuizDetails, *, now: datetime | None = None
) -> Quiz:
    """The teacher stays the same."""
    with transaction.atomic():
        locked = _locked_quiz(quiz, now)
        if details.teacher.pk != locked.teacher_id:
            raise ValidationError({"teacher": "The teacher cannot change."})
        _check_quiz(locked.institute, details, locked, now or timezone.now())
        return _apply_quiz(locked, details)


def bank_choices(quiz: Quiz) -> Any:
    """The teacher's questions of the quiz's subject that are not in it."""
    return (
        Question.objects.filter(teacher_id=quiz.teacher_id, subject_id=quiz.subject_id)
        .exclude(quiz_items__quiz=quiz)
        .prefetch_related("options")
        .order_by("-updated_at", "-pk")
    )


def add_questions(
    quiz: Quiz, questions: list[Question], *, now: datetime | None = None
) -> int:
    """Add bank questions at the end; returns how many were added."""
    with transaction.atomic():
        locked = _locked_quiz(quiz, now)
        for question in questions:
            if (
                question.teacher_id != locked.teacher_id
                or question.subject_id != locked.subject_id
            ):
                raise ValidationError(
                    "Choose questions of this subject from your bank."
                )
        items = QuizQuestion.objects.filter(quiz=locked)
        taken = set(items.values_list("question_id", flat=True))
        position = max(items.values_list("position", flat=True), default=0)
        added = 0
        for question in questions:
            if question.pk in taken:
                continue
            position += 1
            QuizQuestion.objects.create(
                institute=locked.institute,
                quiz=locked,
                question=question,
                position=position,
            )
            taken.add(question.pk)
            added += 1
        return added


def remove_question(
    quiz: Quiz, item: QuizQuestion, *, now: datetime | None = None
) -> None:
    with transaction.atomic():
        locked = _locked_quiz(quiz, now)
        if item.quiz_id != locked.pk:
            raise ValidationError("This question is not in this quiz.")
        item.delete()


def publish_quiz(quiz: Quiz, *, now: datetime | None = None) -> Quiz:
    """Students see a published quiz; it opens at its time (SPEC 6.8)."""
    now = now or timezone.now()
    with transaction.atomic():
        locked = _locked_quiz(quiz, now)
        total = quiz_total(locked)
        if not total:
            raise ValidationError("Add at least one question first.")
        if locked.opens_at <= now:
            raise ValidationError("The opening time has passed. Choose a new one.")
        if locked.pass_marks is not None and locked.pass_marks > total:
            raise ValidationError(f"Pass marks are more than the total ({total}).")
        locked.is_published = True
        locked.save()
        return locked


def unpublish_quiz(quiz: Quiz, *, now: datetime | None = None) -> Quiz:
    """Back to a draft, before it opens."""
    with transaction.atomic():
        locked = _locked_quiz(quiz, now)
        locked.is_published = False
        locked.save()
        return locked


def list_quizzes(user: Any, *, kind: str = "", status: str = "") -> list[Quiz]:
    """The viewer's quizzes, the latest opening first, each with
    ``question_count`` and ``total_marks``."""
    rows = (
        Quiz.objects.for_user(user)
        .select_related("batch", "subject", "teacher__user")
        .annotate(
            question_count=Count("items"),
            total_marks=Sum("items__question__marks"),
        )
    )
    if kind:
        rows = rows.filter(kind=kind)
    quizzes = list(rows)
    if status:
        now = timezone.now()
        quizzes = [quiz for quiz in quizzes if quiz_status(quiz, now) == status]
    return quizzes


def question_in_opened_quiz(question: Question, now: datetime | None = None) -> bool:
    """A question of a quiz that has opened is fixed (backlog AS6)."""
    return QuizQuestion.objects.filter(
        question=question,
        quiz__is_published=True,
        quiz__opens_at__lte=now or timezone.now(),
    ).exists()
