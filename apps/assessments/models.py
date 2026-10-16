"""Assignments (roadmap 5.1, SPEC 4.16 and 6.8), the question bank
(roadmap 5.2) and quizzes and exams (roadmap 5.3).

A teacher publishes an assignment to one batch and subject. Each student
enrolled in that batch and subject sends one text answer before the due
time, and the teacher grades it with marks and feedback.

No submission row means "pending" before the due time and "missed" after
it. A row without marks is "submitted"; a row with marks is "graded".
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.core.managers import TenantManager, TenantQuerySet, UnscopedTenantManager
from apps.core.models import TenantModel
from apps.core.roles import INSTITUTE_WIDE_ROLES, Role, user_role

MAX_TOTAL_MARKS = 1000
MAX_QUESTION_MARKS = 100
MIN_OPTIONS = 2
MAX_OPTIONS = 6
MIN_QUIZ_MINUTES = 5
MAX_QUIZ_MINUTES = 300
# SPEC 6.8: a quiz closes 10 minutes after opens + duration.
QUIZ_GRACE_MINUTES = 10

# A student or guardian sees an assignment through an enrolment in its
# batch and subject, or through their own answer. The 2 enrolment conditions
# sit in one Q, so they must hold on the same enrolment row (the same rule
# as lectures).
_ENROLMENT = "subject__student_links__"
STUDENT_LOOKUPS = {
    Role.STUDENT: f"{_ENROLMENT}student__user_id",
    Role.GUARDIAN: f"{_ENROLMENT}student__guardian_links__guardian__user_id",
}

# From a submission to the user who may see it, by role.
SUBMISSION_LOOKUPS = {
    Role.TEACHER: "assignment__teacher__user_id",
    Role.STUDENT: "student__user_id",
    Role.GUARDIAN: "student__guardian_links__guardian__user_id",
}


def _enrolled_or_own(lookup: str, own: str, user_id: Any) -> Q:
    """An enrolment in the row's batch and subject, or the student's own
    answer or attempt (backlog AS12: a student who left the batch still
    opens their work)."""
    enrolled = Q(**{lookup: user_id, f"{_ENROLMENT}batch_id": F("batch_id")})
    return enrolled | Q(**{own: user_id})


class SubmissionStatus(models.TextChoices):
    """SPEC 2. Not stored: it comes from the row and the due time."""

    PENDING = "pending", "Pending"
    SUBMITTED = "submitted", "Submitted"
    GRADED = "graded", "Graded"
    MISSED = "missed", "Missed"


class AssignmentQuerySet(TenantQuerySet):
    """Admins see the institute, a teacher their own assignments, a student
    or guardian the assignments of their (child's) batch and subject, and
    the ones they (their child) answered."""

    def for_user(self, user: Any) -> AssignmentQuerySet:
        scoped = super().for_user(user)
        role = user_role(user)
        user_id = getattr(user, "pk", None)
        if role in INSTITUTE_WIDE_ROLES:
            return scoped
        if role == Role.TEACHER:
            return scoped.filter(teacher__user_id=user_id)
        lookup = STUDENT_LOOKUPS.get(role or "")
        if lookup is None:
            return scoped.none()
        own = f"submissions__{SUBMISSION_LOOKUPS[role]}"
        return scoped.filter(_enrolled_or_own(lookup, own, user_id)).distinct()


class SubmissionQuerySet(TenantQuerySet):
    """Admins see the institute, a teacher the answers to their own
    assignments, a student their own answers, a guardian their children's."""

    def for_user(self, user: Any) -> SubmissionQuerySet:
        scoped = super().for_user(user)
        role = user_role(user)
        if role in INSTITUTE_WIDE_ROLES:
            return scoped
        lookup = SUBMISSION_LOOKUPS.get(role or "")
        if lookup is None:
            return scoped.none()
        return scoped.filter(**{lookup: getattr(user, "pk", None)}).distinct()


class SameInstituteMixin:
    """Related rows must belong to the row's institute."""

    same_institute: tuple[str, ...] = ()

    def check_institutes(self) -> None:
        for name in self.same_institute:
            related = getattr(self, name, None)
            if related is not None and related.institute_id != self.institute_id:
                raise ValidationError({name: "Must belong to the same institute."})


class Assignment(SameInstituteMixin, TenantModel):
    title = models.CharField(max_length=200)
    instructions = models.TextField()
    teacher = models.ForeignKey(
        "people.TeacherProfile", on_delete=models.PROTECT, related_name="assignments"
    )
    batch = models.ForeignKey(
        "academics.Batch", on_delete=models.PROTECT, related_name="assignments"
    )
    subject = models.ForeignKey(
        "academics.Subject", on_delete=models.PROTECT, related_name="assignments"
    )
    total_marks = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(MAX_TOTAL_MARKS)]
    )
    due_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager.from_queryset(AssignmentQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(AssignmentQuerySet)()

    same_institute = ("teacher", "batch", "subject")

    class Meta:
        ordering = ["-due_at", "-pk"]

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        super().clean()
        self.check_institutes()

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)


class Submission(SameInstituteMixin, TenantModel):
    """One answer per assignment and student; marks and feedback once the
    teacher grades it."""

    assignment = models.ForeignKey(
        Assignment, on_delete=models.PROTECT, related_name="submissions"
    )
    student = models.ForeignKey(
        "people.StudentProfile",
        on_delete=models.PROTECT,
        related_name="assignment_submissions",
    )
    answer = models.TextField()
    submitted_at = models.DateTimeField()
    marks = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    feedback = models.TextField(blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    objects = TenantManager.from_queryset(SubmissionQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(SubmissionQuerySet)()

    same_institute = ("assignment", "student")

    class Meta:
        ordering = ["assignment_id", "student_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "student"],
                name="submission_assignment_student_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student} - {self.assignment}"

    @property
    def is_graded(self) -> bool:
        return self.marks is not None

    def clean(self) -> None:
        super().clean()
        self.check_institutes()
        assignment = getattr(self, "assignment", None)
        if (
            self.marks is not None
            and assignment is not None
            and self.marks > assignment.total_marks
        ):
            raise ValidationError({"marks": "Marks are more than the total marks."})

    def save(self, *args: Any, **kwargs: Any) -> None:
        # The fail-closed manager would hide rows from unique checks; the
        # database constraint enforces uniqueness instead.
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)


# Question bank (roadmap 5.2, SPEC 4.16)


class QuestionKind(models.TextChoices):
    MCQ = "mcq", "MCQ"
    SHORT = "short", "Short answer"


# From a question row to the user who may see it, by role.
QUESTION_LOOKUPS = {Role.TEACHER: "teacher__user_id"}
OPTION_LOOKUPS = {Role.TEACHER: "question__teacher__user_id"}


class QuestionQuerySet(TenantQuerySet):
    """Admins see the institute, a teacher their own bank. Students and
    guardians see questions only inside a quiz (roadmap 5.3)."""

    def for_user(self, user: Any) -> QuestionQuerySet:
        scoped = super().for_user(user)
        role = user_role(user)
        if role in INSTITUTE_WIDE_ROLES:
            return scoped
        lookup = QUESTION_LOOKUPS.get(role or "")
        if lookup is None:
            return scoped.none()
        return scoped.filter(**{lookup: getattr(user, "pk", None)})


class QuestionOptionQuerySet(TenantQuerySet):
    """The same rule as the questions: the correct option is not for
    students."""

    def for_user(self, user: Any) -> QuestionOptionQuerySet:
        scoped = super().for_user(user)
        role = user_role(user)
        if role in INSTITUTE_WIDE_ROLES:
            return scoped
        lookup = OPTION_LOOKUPS.get(role or "")
        if lookup is None:
            return scoped.none()
        return scoped.filter(**{lookup: getattr(user, "pk", None)})


class Question(SameInstituteMixin, TenantModel):
    """One question in a teacher's bank. An MCQ question has 2 to 6
    options with one correct; a short answer question has none (the
    teacher marks the answer)."""

    teacher = models.ForeignKey(
        "people.TeacherProfile", on_delete=models.PROTECT, related_name="questions"
    )
    subject = models.ForeignKey(
        "academics.Subject", on_delete=models.PROTECT, related_name="questions"
    )
    kind = models.CharField(max_length=8, choices=QuestionKind.choices)
    text = models.TextField()
    marks = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(MAX_QUESTION_MARKS)]
    )
    explanation = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager.from_queryset(QuestionQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(QuestionQuerySet)()

    same_institute = ("teacher", "subject")

    class Meta:
        ordering = ["-updated_at", "-pk"]

    def __str__(self) -> str:
        return self.text[:60]

    def clean(self) -> None:
        super().clean()
        self.check_institutes()

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)


class QuestionOption(SameInstituteMixin, TenantModel):
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="options"
    )
    position = models.PositiveSmallIntegerField()  # 1 to 6, in the form's order
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    objects = TenantManager.from_queryset(QuestionOptionQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(QuestionOptionQuerySet)()

    same_institute = ("question",)

    class Meta:
        ordering = ["question_id", "position"]
        constraints = [
            models.UniqueConstraint(
                fields=["question", "position"], name="option_question_position_unique"
            ),
        ]

    def __str__(self) -> str:
        return self.text

    def clean(self) -> None:
        super().clean()
        self.check_institutes()

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)


# Quizzes and exams (roadmap 5.3, SPEC 4.16 and 6.8)


class QuizKind(models.TextChoices):
    QUIZ = "quiz", "Quiz"
    EXAM = "exam", "Exam"


class QuizStatus(models.TextChoices):
    """SPEC 2. Not stored: it comes from ``is_published`` and the time."""

    DRAFT = "draft", "Draft"
    SCHEDULED = "scheduled", "Scheduled"
    LIVE = "live", "Live"
    CLOSED = "closed", "Closed"


class QuizQuerySet(TenantQuerySet):
    """Admins see the institute, a teacher their own quizzes, a student or
    guardian the published quizzes of their (child's) batch and subject,
    and the ones they (their child) attempted."""

    def for_user(self, user: Any) -> QuizQuerySet:
        scoped = super().for_user(user)
        role = user_role(user)
        user_id = getattr(user, "pk", None)
        if role in INSTITUTE_WIDE_ROLES:
            return scoped
        if role == Role.TEACHER:
            return scoped.filter(teacher__user_id=user_id)
        lookup = STUDENT_LOOKUPS.get(role or "")
        if lookup is None:
            return scoped.none()
        own = f"attempts__{ATTEMPT_LOOKUPS[role]}"
        return scoped.filter(
            _enrolled_or_own(lookup, own, user_id), is_published=True
        ).distinct()


class Quiz(SameInstituteMixin, TenantModel):
    """A timed paper for one batch and subject. Its questions come from the
    teacher's bank (``QuizQuestion``)."""

    title = models.CharField(max_length=200)
    kind = models.CharField(
        max_length=8, choices=QuizKind.choices, default=QuizKind.QUIZ
    )
    teacher = models.ForeignKey(
        "people.TeacherProfile", on_delete=models.PROTECT, related_name="quizzes"
    )
    batch = models.ForeignKey(
        "academics.Batch", on_delete=models.PROTECT, related_name="quizzes"
    )
    subject = models.ForeignKey(
        "academics.Subject", on_delete=models.PROTECT, related_name="quizzes"
    )
    opens_at = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(MIN_QUIZ_MINUTES),
            MaxValueValidator(MAX_QUIZ_MINUTES),
        ]
    )
    pass_marks = models.PositiveSmallIntegerField(null=True, blank=True)
    shuffle_questions = models.BooleanField(default=False)
    require_full_screen = models.BooleanField(default=False)
    flag_tab_leaving = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    # When "opens soon" went out (roadmap 6.2); cleared on a new time.
    reminded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager.from_queryset(QuizQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(QuizQuerySet)()

    same_institute = ("teacher", "batch", "subject")

    class Meta:
        ordering = ["-opens_at", "-pk"]
        verbose_name_plural = "quizzes"

    def __str__(self) -> str:
        return self.title

    @property
    def closes_at(self) -> datetime:
        """SPEC 6.8: opens + duration + 10 minutes."""
        return self.opens_at + timedelta(
            minutes=self.duration_minutes + QUIZ_GRACE_MINUTES
        )

    def clean(self) -> None:
        super().clean()
        self.check_institutes()

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)


QUIZ_QUESTION_LOOKUPS = {Role.TEACHER: "quiz__teacher__user_id"}


class QuizQuestionQuerySet(TenantQuerySet):
    """Admins see the institute, a teacher their own quizzes' questions.
    Students get the questions of an attempt from the attempt (5.3)."""

    def for_user(self, user: Any) -> QuizQuestionQuerySet:
        scoped = super().for_user(user)
        role = user_role(user)
        if role in INSTITUTE_WIDE_ROLES:
            return scoped
        lookup = QUIZ_QUESTION_LOOKUPS.get(role or "")
        if lookup is None:
            return scoped.none()
        return scoped.filter(**{lookup: getattr(user, "pk", None)})


class QuizQuestion(SameInstituteMixin, TenantModel):
    """A bank question in a quiz. ``PROTECT``: a question in a quiz stays in
    the bank (backlog AS6)."""

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="items")
    question = models.ForeignKey(
        Question, on_delete=models.PROTECT, related_name="quiz_items"
    )
    position = models.PositiveSmallIntegerField()

    objects = TenantManager.from_queryset(QuizQuestionQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(QuizQuestionQuerySet)()

    same_institute = ("quiz", "question")

    class Meta:
        ordering = ["quiz_id", "position", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["quiz", "question"], name="quiz_question_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quiz} - {self.question}"

    def clean(self) -> None:
        super().clean()
        self.check_institutes()

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)


# Quiz attempts (roadmap 5.3, SPEC 6.8)


class AttemptStatus(models.TextChoices):
    IN_PROGRESS = "in_progress", "In progress"
    SUBMITTED = "submitted", "Submitted"
    GRADED = "graded", "Graded"


ATTEMPT_LOOKUPS = {
    Role.TEACHER: "quiz__teacher__user_id",
    Role.STUDENT: "student__user_id",
    Role.GUARDIAN: "student__guardian_links__guardian__user_id",
}
ANSWER_LOOKUPS = {
    Role.TEACHER: "attempt__quiz__teacher__user_id",
    Role.STUDENT: "attempt__student__user_id",
}


class AttemptQuerySet(TenantQuerySet):
    """Admins see the institute, a teacher the attempts at their quizzes, a
    student their own, a guardian their children's."""

    def for_user(self, user: Any) -> AttemptQuerySet:
        scoped = super().for_user(user)
        role = user_role(user)
        if role in INSTITUTE_WIDE_ROLES:
            return scoped
        lookup = ATTEMPT_LOOKUPS.get(role or "")
        if lookup is None:
            return scoped.none()
        return scoped.filter(**{lookup: getattr(user, "pk", None)}).distinct()


class AttemptAnswerQuerySet(TenantQuerySet):
    """Admins see the institute, a teacher the answers at their quizzes, a
    student their own. Guardians see scores, not answers (SPEC 6.8)."""

    def for_user(self, user: Any) -> AttemptAnswerQuerySet:
        scoped = super().for_user(user)
        role = user_role(user)
        if role in INSTITUTE_WIDE_ROLES:
            return scoped
        lookup = ANSWER_LOOKUPS.get(role or "")
        if lookup is None:
            return scoped.none()
        return scoped.filter(**{lookup: getattr(user, "pk", None)})


class QuizAttempt(SameInstituteMixin, TenantModel):
    """A student's one attempt at a quiz (SPEC 6.8). ``deadline`` is fixed at
    the start: the duration from then, but no later than the quiz closes.
    ``question_order`` keeps the order this student sees (shuffled or not)."""

    quiz = models.ForeignKey(Quiz, on_delete=models.PROTECT, related_name="attempts")
    student = models.ForeignKey(
        "people.StudentProfile",
        on_delete=models.PROTECT,
        related_name="quiz_attempts",
    )
    status = models.CharField(
        max_length=16,
        choices=AttemptStatus.choices,
        default=AttemptStatus.IN_PROGRESS,
    )
    started_at = models.DateTimeField()
    deadline = models.DateTimeField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    auto_submitted = models.BooleanField(default=False)
    question_order = ArrayField(models.PositiveBigIntegerField(), default=list)
    score = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)

    objects = TenantManager.from_queryset(AttemptQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(AttemptQuerySet)()

    same_institute = ("quiz", "student")

    class Meta:
        ordering = ["quiz_id", "student_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["quiz", "student"], name="attempt_quiz_student_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student} - {self.quiz}"

    def clean(self) -> None:
        super().clean()
        self.check_institutes()

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)


class AttemptAnswer(SameInstituteMixin, TenantModel):
    """One answer in an attempt: the chosen option (MCQ) or text (short
    answer). ``marks`` is set at submit for an MCQ, by the teacher for a
    short answer."""

    attempt = models.ForeignKey(
        QuizAttempt, on_delete=models.CASCADE, related_name="answers"
    )
    item = models.ForeignKey(
        QuizQuestion, on_delete=models.PROTECT, related_name="answers"
    )
    option = models.ForeignKey(
        QuestionOption,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    text = models.TextField(blank=True)
    marks = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)

    objects = TenantManager.from_queryset(AttemptAnswerQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(AttemptAnswerQuerySet)()

    same_institute = ("attempt", "item")

    class Meta:
        ordering = ["attempt_id", "item_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "item"], name="answer_attempt_item_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.attempt} - {self.item.position}"

    def clean(self) -> None:
        super().clean()
        self.check_institutes()

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)


# Exam mode (roadmap 5.3 part 2c, SPEC 6.8)


class AttemptEventKind(models.TextChoices):
    LEFT_PAGE = "left_page", "Left the page"
    LEFT_FULL_SCREEN = "left_full_screen", "Left full screen"


EVENT_LOOKUPS = {Role.TEACHER: "attempt__quiz__teacher__user_id"}


class AttemptEventQuerySet(TenantQuerySet):
    """Admins see the institute, a teacher the flags at their quizzes.
    Students and guardians do not read them."""

    def for_user(self, user: Any) -> AttemptEventQuerySet:
        scoped = super().for_user(user)
        role = user_role(user)
        if role in INSTITUTE_WIDE_ROLES:
            return scoped
        lookup = EVENT_LOOKUPS.get(role or "")
        if lookup is None:
            return scoped.none()
        return scoped.filter(**{lookup: getattr(user, "pk", None)})


class AttemptEvent(SameInstituteMixin, TenantModel):
    """One exam flag in an attempt: the student left the page or full
    screen. Shown to the teacher; it never changes the score."""

    attempt = models.ForeignKey(
        QuizAttempt, on_delete=models.CASCADE, related_name="events"
    )
    kind = models.CharField(max_length=20, choices=AttemptEventKind.choices)
    at = models.DateTimeField()

    objects = TenantManager.from_queryset(AttemptEventQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(AttemptEventQuerySet)()

    same_institute = ("attempt",)

    class Meta:
        ordering = ["attempt_id", "at", "pk"]

    def __str__(self) -> str:
        return f"{self.attempt} - {self.get_kind_display()}"

    def clean(self) -> None:
        super().clean()
        self.check_institutes()

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)
