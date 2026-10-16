"""Publish, submit and grade assignments (roadmap 5.1, SPEC 4.16 and 6.8),
keep the teacher's question bank (roadmap 5.2), set up quizzes and exams
and run the students' attempts (roadmap 5.3).

A student is expected to answer an assignment when an enrolment of theirs
has the assignment's batch and subject and was made before the due time.
A student who already answered is expected too, so an answer stays listed
after the enrolment is removed. An inactive student (one who left) is
expected only where they answered.

Answers are taken until the due time; after it, a student with no answer
has "Missed" (SPEC 6.8 allows late answers for homework only).
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
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
    AttemptAnswer,
    AttemptEvent,
    AttemptEventKind,
    AttemptStatus,
    Question,
    QuestionKind,
    QuestionOption,
    Quiz,
    QuizAttempt,
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
    """Answers to the viewer's assignments with no marks yet, and submitted
    quiz attempts with written answers to mark (teacher dashboard, SPEC 8
    "pending reviews"; backlog AS10). An expired attempt that no page has
    submitted yet is not counted (backlog AS9)."""
    answers = Submission.objects.for_user(user).filter(marks__isnull=True).count()
    attempts = (
        QuizAttempt.objects.for_user(user)
        .filter(status=AttemptStatus.SUBMITTED)
        .count()
    )
    return answers + attempts


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


# Quiz attempts (roadmap 5.3, SPEC 6.8)
#
# A student of the quiz's batch and subject starts it while it is live and
# has one attempt. The countdown ends at the attempt's deadline: the
# duration from the start, but no later than the quiz closes. When it ends
# the page sends the answers; answers that arrive more than a minute late
# are not saved, and an attempt left open is submitted with the answers it
# has. MCQ answers are marked at submit; short answers wait for the teacher.

ANSWER_GRACE = timedelta(minutes=1)  # network delay for the timer's submit
NOT_LIVE_MESSAGE = "This quiz is not live."
DONE_MESSAGE = "This attempt is already submitted."


def is_quiz_student(quiz: Quiz, student: StudentProfile) -> bool:
    """An active student enrolled in the quiz's batch and subject."""
    return StudentBatchSubject.objects.filter(
        student=student,
        batch_id=quiz.batch_id,
        subject_id=quiz.subject_id,
        student__status=ProfileStatus.ACTIVE,
    ).exists()


def start_attempt(
    quiz: Quiz, student: StudentProfile, *, now: datetime | None = None
) -> QuizAttempt:
    """Start the student's one attempt, or return it if it exists."""
    now = now or timezone.now()
    with transaction.atomic():
        locked = Quiz.objects.select_for_update().get(pk=quiz.pk)
        existing = QuizAttempt.objects.filter(quiz=locked, student=student).first()
        if existing is not None:
            return existing
        if quiz_status(locked, now) != QuizStatus.LIVE:
            raise ValidationError(NOT_LIVE_MESSAGE)
        if not is_quiz_student(locked, student):
            raise ValidationError("This quiz is not for this student.")
        order = [item.pk for item in quiz_items(locked)]
        if locked.shuffle_questions:
            random.SystemRandom().shuffle(order)
        attempt = QuizAttempt(
            institute=locked.institute,
            quiz=locked,
            started_at=now,
            deadline=min(
                now + timedelta(minutes=locked.duration_minutes), locked.closes_at
            ),
            question_order=order,
        )
        attempt.student = student
        attempt.save()
        return attempt


def attempt_items(attempt: QuizAttempt) -> list[QuizQuestion]:
    """The attempt's questions in the order this student sees them."""
    items = {item.pk: item for item in quiz_items(attempt.quiz)}
    return [items[pk] for pk in attempt.question_order if pk in items]


def attempt_answers(attempt: QuizAttempt) -> dict[int, AttemptAnswer]:
    return {row.item_id: row for row in AttemptAnswer.objects.filter(attempt=attempt)}


def _write_answers(
    attempt: QuizAttempt, items: list[QuizQuestion], answers: dict[int, Any]
) -> None:
    """``answers`` maps an item pk to an option pk (MCQ) or text (short)."""
    saved = attempt_answers(attempt)
    for item in items:
        if item.pk not in answers:
            continue
        value = answers[item.pk]
        row = saved.get(item.pk) or AttemptAnswer(
            institute=attempt.institute, attempt=attempt, item=item
        )
        if item.question.kind == QuestionKind.MCQ:
            options = {str(option.pk): option for option in item.question.options.all()}
            if value not in (None, "") and str(value) not in options:
                raise ValidationError("Choose one of the question's options.")
            row.option = options.get(str(value))
        else:
            row.text = str(value or "").strip()
        row.save()


def _finish(
    attempt: QuizAttempt, items: list[QuizQuestion], *, auto: bool, now: datetime
) -> None:
    """Mark the MCQ answers; graded at once when there is no short answer."""
    saved = attempt_answers(attempt)
    short = False
    total = Decimal(0)
    for item in items:
        question = item.question
        if question.kind == QuestionKind.SHORT:
            short = True
            continue
        row = saved.get(item.pk) or AttemptAnswer(
            institute=attempt.institute, attempt=attempt, item=item
        )
        right = row.option is not None and row.option.is_correct
        row.marks = Decimal(question.marks) if right else Decimal(0)
        row.save()
        total += row.marks
    attempt.status = AttemptStatus.SUBMITTED if short else AttemptStatus.GRADED
    attempt.score = None if short else total
    attempt.submitted_at = min(now, attempt.deadline)
    attempt.auto_submitted = auto
    attempt.save()


def save_attempt(
    attempt: QuizAttempt,
    answers: dict[int, Any],
    *,
    submit: bool = False,
    auto: bool = False,
    now: datetime | None = None,
) -> QuizAttempt:
    """Save the answers; ``submit`` ends the attempt. Answers that arrive
    after the deadline and its grace minute are not saved, and the attempt
    is submitted with what it has."""
    now = now or timezone.now()
    with transaction.atomic():
        locked = QuizAttempt.objects.select_for_update().get(pk=attempt.pk)
        if locked.status != AttemptStatus.IN_PROGRESS:
            raise ValidationError(DONE_MESSAGE)
        items = attempt_items(locked)
        late = now > locked.deadline + ANSWER_GRACE
        if not late:
            _write_answers(locked, items, answers)
        if submit or late:
            _finish(locked, items, auto=auto or late, now=now)
        return locked


def close_expired(attempt: QuizAttempt, *, now: datetime | None = None) -> QuizAttempt:
    """Submit an attempt left open past its deadline (the student closed the
    page). Pages call this before they show an attempt."""
    now = now or timezone.now()
    if (
        attempt.status != AttemptStatus.IN_PROGRESS
        or now <= attempt.deadline + ANSWER_GRACE
    ):
        return attempt
    return save_attempt(attempt, {}, auto=True, now=now)


@dataclass(frozen=True)
class StudentQuiz:
    quiz: Quiz
    attempt: QuizAttempt | None
    status: str  # the quiz status (SPEC 2)


def student_quizzes(
    student: StudentProfile, *, now: datetime | None = None
) -> list[StudentQuiz]:
    """The published quizzes of the student's batches and subjects, the
    live and next ones first, then the newest closed ones."""
    now = now or timezone.now()
    links = StudentBatchSubject.objects.filter(
        student=student, student__status=ProfileStatus.ACTIVE
    ).values_list("batch_id", "subject_id")
    enrolled = Q(pk__in=[])
    for batch_id, link_subject_id in links:
        enrolled |= Q(batch_id=batch_id, subject_id=link_subject_id)
    attempts = {
        row.quiz_id: close_expired(row, now=now)
        for row in QuizAttempt.objects.filter(student=student)
    }
    quizzes = Quiz.objects.filter(enrolled | Q(pk__in=attempts), is_published=True)
    rows = [
        StudentQuiz(quiz, attempts.get(quiz.pk), quiz_status(quiz, now))
        for quiz in quizzes.select_related("subject").annotate(
            total_marks=Sum("items__question__marks")
        )
    ]
    open_rows = sorted(
        (row for row in rows if row.status != QuizStatus.CLOSED),
        key=lambda row: (row.quiz.opens_at, row.quiz.pk),
    )
    closed = sorted(
        (row for row in rows if row.status == QuizStatus.CLOSED),
        key=lambda row: (row.quiz.opens_at, row.quiz.pk),
        reverse=True,
    )
    return open_rows + closed


# Quiz results and marking (roadmap 5.3 part 2b, SPEC 6.8)
#
# The teacher sees every student of the quiz's batch and subject with their
# attempt, and marks the short answers of a submitted attempt. Marking all
# of them makes the attempt graded, with the score of every answer. The
# marks can change later.

MARK_OPEN_MESSAGE = "The student is still answering. Mark the attempt after it ends."


@dataclass(frozen=True)
class ResultRow:
    student: StudentProfile
    attempt: QuizAttempt | None


def quiz_results(quiz: Quiz, *, now: datetime | None = None) -> list[ResultRow]:
    """The quiz's students by name, with their attempts. An attempt left
    open past its deadline is submitted first (backlog AS9)."""
    now = now or timezone.now()
    attempts = {
        row.student_id: close_expired(row, now=now)
        for row in QuizAttempt.objects.filter(quiz=quiz)
    }
    enrolled = StudentBatchSubject.objects.filter(
        batch_id=quiz.batch_id,
        subject_id=quiz.subject_id,
        student__status=ProfileStatus.ACTIVE,
    ).values_list("student_id", flat=True)
    students = (
        StudentProfile.objects.filter(pk__in=set(enrolled) | set(attempts))
        .select_related("user")
        .order_by("user__first_name", "user__last_name", "pk")
    )
    return [ResultRow(student, attempts.get(student.pk)) for student in students]


@dataclass(frozen=True)
class QuizCount:
    attempts: int
    to_mark: int  # submitted, waiting for the teacher
    total: int  # the quiz's students, and any other student with an attempt


def quiz_counts(quizzes: list[Quiz]) -> dict[int, QuizCount]:
    """Attempts / Total for a page of quizzes, in 2 queries."""
    if not quizzes:
        return {}
    links = list(
        StudentBatchSubject.objects.filter(
            batch_id__in={quiz.batch_id for quiz in quizzes},
            student__status=ProfileStatus.ACTIVE,
        ).values_list("student_id", "batch_id", "subject_id")
    )
    attempts: dict[int, dict[int, str]] = defaultdict(dict)
    rows = QuizAttempt.objects.filter(quiz__in=quizzes).values_list(
        "quiz_id", "student_id", "status"
    )
    for quiz_id, student_id, status in rows:
        attempts[quiz_id][student_id] = status
    counts = {}
    for quiz in quizzes:
        own = attempts[quiz.pk]
        expected = {
            student_id
            for student_id, batch_id, subject_id in links
            if batch_id == quiz.batch_id and subject_id == quiz.subject_id
        }
        counts[quiz.pk] = QuizCount(
            attempts=len(own),
            to_mark=sum(status == AttemptStatus.SUBMITTED for status in own.values()),
            total=len(expected | set(own)),
        )
    return counts


@dataclass(frozen=True)
class AnswerRow:
    number: int
    item: QuizQuestion
    answer: AttemptAnswer | None


def attempt_review(attempt: QuizAttempt) -> list[AnswerRow]:
    """Each question in the student's order, with the student's answer."""
    answers = {
        row.item_id: row
        for row in AttemptAnswer.objects.filter(attempt=attempt).select_related(
            "option"
        )
    }
    return [
        AnswerRow(number, item, answers.get(item.pk))
        for number, item in enumerate(attempt_items(attempt), start=1)
    ]


def mark_attempt(attempt: QuizAttempt, marks: dict[int, Decimal]) -> QuizAttempt:
    """Save the marks of the short answers (``marks`` maps an item pk to
    marks). Every short answer needs marks; the attempt is then graded with
    the sum of all its answers' marks."""
    with transaction.atomic():
        locked = QuizAttempt.objects.select_for_update().get(pk=attempt.pk)
        if locked.status == AttemptStatus.IN_PROGRESS:
            raise ValidationError(MARK_OPEN_MESSAGE)
        items = attempt_items(locked)
        saved = attempt_answers(locked)
        for number, item in enumerate(items, start=1):
            question = item.question
            if question.kind != QuestionKind.SHORT:
                continue
            value = marks.get(item.pk)
            if value is None or not 0 <= value <= question.marks:
                raise ValidationError(
                    f"Question {number}: give 0 to {question.marks} marks."
                )
            row = saved.get(item.pk) or AttemptAnswer(
                institute=locked.institute, attempt=locked, item=item
            )
            row.marks = value
            row.save()
            saved[item.pk] = row
        locked.score = sum(
            (row.marks for row in saved.values() if row.marks is not None),
            Decimal(0),
        )
        locked.status = AttemptStatus.GRADED
        locked.save()
        return locked


def short_items(attempt: QuizAttempt) -> list[tuple[int, QuizQuestion]]:
    """The short answer questions of an attempt, with their numbers."""
    return [
        (number, item)
        for number, item in enumerate(attempt_items(attempt), start=1)
        if item.question.kind == QuestionKind.SHORT
    ]


# Exam mode (roadmap 5.3 part 2c, SPEC 6.8)
#
# An exam can flag leaving the page and require full screen. The paper
# posts a flag when the student leaves; the teacher sees the flags with the
# attempt. Flags never change the score or end the attempt.

MAX_EVENTS = 200  # per attempt: a page that loops cannot fill the table


def flagged_kinds(quiz: Quiz) -> set[str]:
    """The flags this quiz records (only an exam has any)."""
    if quiz.kind != QuizKind.EXAM:
        return set()
    kinds = set()
    if quiz.flag_tab_leaving:
        kinds.add(AttemptEventKind.LEFT_PAGE)
    if quiz.require_full_screen:
        kinds.add(AttemptEventKind.LEFT_FULL_SCREEN)
    return kinds


def log_attempt_event(
    attempt: QuizAttempt, kind: str, *, now: datetime | None = None
) -> AttemptEvent | None:
    """Record a flag of an attempt in progress, before its deadline and its
    grace minute. Returns None when it is not recorded."""
    now = now or timezone.now()
    with transaction.atomic():
        locked = QuizAttempt.objects.select_for_update().get(pk=attempt.pk)
        if (
            locked.status != AttemptStatus.IN_PROGRESS
            or now > locked.deadline + ANSWER_GRACE
            or kind not in flagged_kinds(locked.quiz)
            or AttemptEvent.objects.filter(attempt=locked).count() >= MAX_EVENTS
        ):
            return None
        return AttemptEvent.objects.create(
            institute=locked.institute, attempt=locked, kind=kind, at=now
        )


def attempt_events(attempt: QuizAttempt) -> list[AttemptEvent]:
    return list(AttemptEvent.objects.filter(attempt=attempt))


def event_counts(quiz: Quiz) -> dict[int, dict[str, int]]:
    """For each attempt of the quiz: how many flags of each kind."""
    counts: dict[int, dict[str, int]] = defaultdict(dict)
    rows = (
        AttemptEvent.objects.filter(attempt__quiz=quiz)
        .values_list("attempt_id", "kind")
        .annotate(total=Count("pk"))
        .order_by()
    )
    for attempt_id, kind, total in rows:
        counts[attempt_id][kind] = total
    return dict(counts)
