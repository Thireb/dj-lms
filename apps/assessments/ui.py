"""Assignment badges, tables and cards (roadmap 5.1, SPEC 2 and 3), and
the question bank table (roadmap 5.2) and the quiz tables (roadmap 5.3)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django import forms
from django.urls import reverse
from django.utils import timezone
from django.utils.text import Truncator

from apps.assessments.models import (
    Assignment,
    AttemptStatus,
    Question,
    QuestionKind,
    Quiz,
    QuizAttempt,
    QuizKind,
    QuizQuestion,
    QuizStatus,
    SubmissionStatus,
)
from apps.assessments.services import (
    AnswerRow,
    AssignmentCount,
    QuizCount,
    ResultRow,
    StudentAssignment,
    StudentQuiz,
    SubmissionRow,
    correct_option,
    has_opened,
    is_open,
    marks_text,
    quiz_status,
)
from apps.lectures.times import local_date, local_time
from apps.ui.components.actions import ConfirmDialog, IconButton, PostButton
from apps.ui.components.block_stack import ButtonRow
from apps.ui.components.data import (
    Badge,
    BadgeNote,
    Column,
    DataTable,
    PersonCell,
)
from apps.ui.components.forms import CrispyForm, PortalPostForm
from apps.ui.components.layout import SectionCard

# SPEC 2: amber, blue, green, red.
STATUS_TONES = {
    SubmissionStatus.PENDING: "warning",
    SubmissionStatus.SUBMITTED: "info",
    SubmissionStatus.GRADED: "success",
    SubmissionStatus.MISSED: "danger",
}


def submission_badge(status: str) -> Badge:
    return Badge(SubmissionStatus(status).label, tone=STATUS_TONES[status])


def when(value: datetime | None) -> str:
    """Example: Mon 14 Oct 2026, 11:59 PM PKT."""
    if value is None:
        return ""
    return f"{local_date(value)}, {local_time(value)}"


def due_text(assignment: Assignment) -> str:
    return when(assignment.due_at)


def open_badge(assignment: Assignment, now: datetime) -> Badge:
    """The teacher's status: answers are taken (Open) or not (Closed)."""
    if is_open(assignment, now):
        return Badge("Open", tone="info")
    return Badge("Closed", tone="neutral")


def assignment_url(portal: str, action: str, assignment: Assignment) -> str:
    return reverse(f"{portal}:assignment_{action}", kwargs={"pk": assignment.pk})


def submitted_total(count: AssignmentCount | None) -> str:
    """Teacher list "Submitted / Total"."""
    if count is None:
        return "0 / 0"
    return f"{count.submitted} / {count.total}"


class TeacherAssignmentTable(DataTable):
    """Teacher "Assignments" (SPEC 3): Title, Batch, Due, Submitted / Total,
    Status; a row opens the answers to grade."""

    empty_title = "No assignments match these filters."

    def __init__(
        self,
        rows: list[Assignment],
        *,
        counts: dict[int, AssignmentCount] | None = None,
        now: datetime | None = None,
        **props,
    ):
        self.counts = counts or {}
        self.now = now or timezone.now()
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("title", "Assignment"),
            Column("batch", "Batch", lambda row: row.batch.name),
            Column("subject", "Subject", lambda row: row.subject.name),
            Column("due", "Due", due_text),
            Column("submitted", "Submitted / Total", self.submitted_total),
            Column("status", "Status", self.status),
            Column("actions", "", self.actions),
        ]

    def submitted_total(self, assignment: Assignment) -> str:
        return submitted_total(self.counts.get(assignment.pk))

    def status(self, assignment: Assignment) -> Any:
        badge = open_badge(assignment, self.now)
        count = self.counts.get(assignment.pk)
        if count is None or not count.to_grade:
            return badge
        return BadgeNote(badge, f"{count.to_grade} to grade")

    def actions(self, assignment: Assignment) -> ButtonRow:
        title = assignment.title
        return ButtonRow(
            items=[
                IconButton(
                    "eye",
                    f"Open {title}",
                    url=assignment_url("teacher", "detail", assignment),
                ),
                IconButton(
                    "square-pen",
                    f"Edit {title}",
                    url=assignment_url("teacher", "edit", assignment),
                ),
            ]
        )


class SubmissionTable(DataTable):
    """The answers to one assignment, on the teacher's assignment page."""

    empty_title = "No students take this batch and subject."

    def __init__(self, rows: list[SubmissionRow], *, assignment: Assignment, **props):
        self.assignment = assignment
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column(
                "student",
                "Student",
                lambda row: PersonCell(
                    str(row.student), detail=row.student.student_code
                ),
            ),
            Column("status", "Status", lambda row: submission_badge(row.status)),
            Column("submitted", "Submitted on", self.submitted_on),
            Column("marks", "Marks", self.marks),
            Column("actions", "", self.grade_button),
        ]

    def submitted_on(self, row: SubmissionRow) -> str:
        return when(row.submission.submitted_at) if row.submission else "-"

    def marks(self, row: SubmissionRow) -> str:
        marks = row.submission.marks if row.submission else None
        return marks_text(marks, self.assignment.total_marks)

    def grade_button(self, row: SubmissionRow) -> Any:
        if row.submission is None:
            return ""
        label = "Change grade" if row.submission.is_graded else "Grade"
        url = reverse(
            "teacher:assignment_grade",
            kwargs={"pk": self.assignment.pk, "submission_pk": row.submission.pk},
        )
        return IconButton("square-pen", f"{label}: {row.student}", url=url)


class StudentAssignmentTable(DataTable):
    """Student "Assignments" (SPEC 3): Title, Subject, Due, Status, Marks."""

    empty_title = "No assignments match these filters."
    portal = "student"

    def __init__(self, rows: list[StudentAssignment], **props):
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("title", "Assignment", lambda row: row.assignment.title),
            Column("subject", "Subject", lambda row: row.assignment.subject.name),
            Column("due", "Due", lambda row: due_text(row.assignment)),
            Column("status", "Status", lambda row: submission_badge(row.status)),
            Column("marks", "Marks", self.marks),
            Column("actions", "", self.open_button),
        ]

    def marks(self, row: StudentAssignment) -> str:
        marks = row.submission.marks if row.submission else None
        return marks_text(marks, row.assignment.total_marks)

    def open_button(self, row: StudentAssignment) -> IconButton:
        url = assignment_url(self.portal, "detail", row.assignment)
        return IconButton("eye", f"Open {row.assignment.title}", url=url)


def assignment_detail_rows(
    assignment: Assignment, *, show_teacher: bool
) -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = [
        ("Batch", assignment.batch.name),
        ("Subject", assignment.subject.name),
        ("Due", due_text(assignment)),
        ("Total marks", str(assignment.total_marks)),
    ]
    if show_teacher:
        rows.insert(2, ("Teacher", str(assignment.teacher)))
    return rows


def form_card(title: str, form: forms.Form, action: str, icon: str) -> SectionCard:
    """A form inside a card on a detail page."""
    form.helper.disable_csrf = True  # PortalPostForm adds the token
    return SectionCard(
        title=title,
        icon=icon,
        body=PortalPostForm(action=action, body=CrispyForm(form=form), framed=False),
    )


# Question bank (roadmap 5.2)

QUESTION_PREVIEW = 90  # characters of the question in the table


def question_url(action: str, question: Question) -> str:
    return reverse(f"teacher:question_{action}", kwargs={"pk": question.pk})


def question_answer(question: Question) -> str:
    """The correct option of an MCQ question; the teacher marks the rest."""
    if question.kind == QuestionKind.SHORT:
        return "Marked by the teacher"
    option = correct_option(question)
    return f"{option.position}. {option.text}" if option else "-"


def delete_question_dialog(question: Question) -> ConfirmDialog:
    return ConfirmDialog(
        "Delete this question from your bank? This cannot be undone.",
        "Delete question",
        url=question_url("delete", question),
        trigger_label="Delete",
        dismiss_label="Keep question",
    )


class QuestionTable(DataTable):
    """Teacher "Question bank": Question, Subject, Type, Marks, Answer."""

    empty_title = "No questions match these filters."

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column(
                "question",
                "Question",
                lambda row: Truncator(row.text).chars(QUESTION_PREVIEW),
            ),
            Column("subject", "Subject", lambda row: row.subject.name),
            Column("kind", "Type", lambda row: row.get_kind_display()),
            Column("marks", "Marks", lambda row: str(row.marks)),
            Column("answer", "Answer", question_answer),
            Column("actions", "", self.actions),
        ]

    def actions(self, question: Question) -> ButtonRow:
        return ButtonRow(
            items=[
                IconButton(
                    "square-pen",
                    f"Edit question: {Truncator(question.text).chars(40)}",
                    url=question_url("edit", question),
                ),
                delete_question_dialog(question),
            ]
        )


# Quizzes and exams (roadmap 5.3)

# SPEC 2: grey, blue, green, grey.
QUIZ_TONES = {
    QuizStatus.DRAFT: "neutral",
    QuizStatus.SCHEDULED: "info",
    QuizStatus.LIVE: "success",
    QuizStatus.CLOSED: "neutral",
}


def quiz_status_badge(status: str) -> Badge:
    return Badge(QuizStatus(status).label, tone=QUIZ_TONES[status])


def quiz_url(action: str, quiz: Quiz, **kwargs: Any) -> str:
    return reverse(f"teacher:quiz_{action}", kwargs={"pk": quiz.pk, **kwargs})


def minutes_text(minutes: int) -> str:
    return f"{minutes} min"


class TeacherQuizTable(DataTable):
    """Teacher "Quizzes and exams" (SPEC 3): Title, Type, Batch, Opens,
    Duration, Attempts, Status (with the attempts to mark)."""

    empty_title = "No quizzes match these filters."

    def __init__(
        self,
        rows: list[Quiz],
        *,
        counts: dict[int, QuizCount] | None = None,
        now: datetime | None = None,
        **props,
    ):
        self.counts = counts or {}
        self.now = now or timezone.now()
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("title", "Title"),
            Column("kind", "Type", lambda quiz: quiz.get_kind_display()),
            Column("batch", "Batch", lambda quiz: quiz.batch.name),
            Column("opens", "Opens", lambda quiz: when(quiz.opens_at)),
            Column("duration", "Duration", lambda q: minutes_text(q.duration_minutes)),
            Column("attempts", "Attempts", self.attempts),
            Column("status", "Status", self.status),
            Column("actions", "", self.actions),
        ]

    def attempts(self, quiz: Quiz) -> str:
        """Example: 12 / 30."""
        count = self.counts.get(quiz.pk)
        return f"{count.attempts} / {count.total}" if count else "0 / 0"

    def status(self, quiz: Quiz) -> Any:
        badge = quiz_status_badge(quiz_status(quiz, self.now))
        count = self.counts.get(quiz.pk)
        if count is None or not count.to_mark:
            return badge
        return BadgeNote(badge, f"{count.to_mark} to mark")

    def actions(self, quiz: Quiz) -> ButtonRow:
        items: list[Any] = [
            IconButton("eye", f"Open {quiz.title}", url=quiz_url("detail", quiz))
        ]
        if not has_opened(quiz, self.now):
            url = quiz_url("edit", quiz)
            items.append(IconButton("square-pen", f"Edit {quiz.title}", url=url))
        return ButtonRow(items=items)


class QuizItemTable(DataTable):
    """The questions of one quiz, in order, on the teacher's quiz page."""

    empty_title = "No questions yet. Add some from your bank."

    def __init__(self, rows: list[QuizQuestion], *, editable: bool, **props):
        self.editable = editable
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        columns = [
            Column("number", "No.", lambda item: str(item.position)),
            Column(
                "question",
                "Question",
                lambda item: Truncator(item.question.text).chars(QUESTION_PREVIEW),
            ),
            Column("kind", "Type", lambda item: item.question.get_kind_display()),
            Column("marks", "Marks", lambda item: str(item.question.marks)),
            Column("answer", "Answer", lambda item: question_answer(item.question)),
        ]
        if self.editable:
            columns.append(Column("actions", "", self.remove_button))
        return columns

    def remove_button(self, item: QuizQuestion) -> PostButton:
        url = quiz_url("remove_question", item.quiz, item_pk=item.pk)
        return PostButton("Remove", url, variant="secondary")


def quiz_detail_rows(quiz: Quiz, *, total: int, now: datetime) -> list[tuple]:
    exam = quiz.kind == QuizKind.EXAM
    rows: list[tuple[str, Any]] = [
        ("Status", quiz_status_badge(quiz_status(quiz, now))),
        ("Type", quiz.get_kind_display()),
        ("Batch", quiz.batch.name),
        ("Subject", quiz.subject.name),
        ("Opens", when(quiz.opens_at)),
        ("Duration", minutes_text(quiz.duration_minutes)),
        ("Closes", when(quiz.closes_at)),
        ("Total marks", str(total)),
        ("Pass marks", "" if quiz.pass_marks is None else str(quiz.pass_marks)),
        ("Shuffle questions", "Yes" if quiz.shuffle_questions else "No"),
    ]
    if exam:
        rows += [
            ("Full screen", "Required" if quiz.require_full_screen else "No"),
            ("Tab leaving", "Flagged" if quiz.flag_tab_leaving else "No"),
        ]
    return rows


# Quiz attempts (roadmap 5.3)

# SPEC 2: blue, amber, green.
ATTEMPT_TONES = {
    AttemptStatus.IN_PROGRESS: "info",
    AttemptStatus.SUBMITTED: "warning",
    AttemptStatus.GRADED: "success",
}
NOT_TAKEN = "Not taken"


def attempt_badge(attempt: QuizAttempt) -> Badge:
    status = AttemptStatus(attempt.status)
    return Badge(status.label, tone=ATTEMPT_TONES[status])


def student_quiz_badge(row: StudentQuiz) -> Badge:
    """The attempt's status once started; before that the quiz status, and
    "Not taken" for a closed quiz without an attempt."""
    if row.attempt is not None:
        return attempt_badge(row.attempt)
    if row.status == QuizStatus.CLOSED:
        return Badge(NOT_TAKEN, tone="danger")
    return quiz_status_badge(row.status)


def score_text(attempt: QuizAttempt | None, total: int | None) -> str:
    """Example: 7 / 10; a dash until graded (SPEC 6.8)."""
    return marks_text(attempt.score if attempt else None, total or 0)


def student_quiz_url(action: str, quiz: Quiz) -> str:
    return reverse(f"student:quiz_{action}", kwargs={"pk": quiz.pk})


class StudentQuizTable(DataTable):
    """Student "Quizzes and exams" (SPEC 3): Title, Type, Opens, Duration,
    Status, Score."""

    empty_title = "No quizzes yet."

    def __init__(self, rows: list[StudentQuiz], **props):
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("title", "Title", lambda row: row.quiz.title),
            Column("kind", "Type", lambda row: row.quiz.get_kind_display()),
            Column("opens", "Opens", lambda row: when(row.quiz.opens_at)),
            Column(
                "duration",
                "Duration",
                lambda row: minutes_text(row.quiz.duration_minutes),
            ),
            Column("status", "Status", student_quiz_badge),
            Column(
                "score",
                "Score",
                lambda row: score_text(row.attempt, row.quiz.total_marks),
            ),
            Column("actions", "", self.open_button),
        ]

    def open_button(self, row: StudentQuiz) -> IconButton:
        url = student_quiz_url("detail", row.quiz)
        return IconButton("eye", f"Open {row.quiz.title}", url=url)


# Quiz results and marking (roadmap 5.3 part 2b)

NO_ANSWER = "No answer"


def result_badge(row: ResultRow, status: str) -> Badge:
    """The attempt's status; without one, "Not taken" once the quiz is
    closed and "Not started" before."""
    if row.attempt is not None:
        return attempt_badge(row.attempt)
    if status == QuizStatus.CLOSED:
        return Badge(NOT_TAKEN, tone="danger")
    return Badge("Not started", tone="neutral")


def teacher_attempt_url(quiz: Quiz, attempt: QuizAttempt) -> str:
    return quiz_url("attempt", quiz, attempt_pk=attempt.pk)


class QuizResultTable(DataTable):
    """The students of one quiz on the teacher's quiz page: Student,
    Status, Submitted, Score; a row opens the answers to mark."""

    empty_title = "No students take this batch and subject."

    def __init__(
        self, rows: list[ResultRow], *, quiz: Quiz, total: int, status: str, **props
    ):
        self.quiz = quiz
        self.total = total
        self.status = status
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column(
                "student",
                "Student",
                lambda row: PersonCell(
                    str(row.student), detail=row.student.student_code
                ),
            ),
            Column("status", "Status", lambda row: result_badge(row, self.status)),
            Column("submitted", "Submitted", self.submitted),
            Column("score", "Score", lambda row: score_text(row.attempt, self.total)),
            Column("actions", "", self.open_button),
        ]

    def submitted(self, row: ResultRow) -> str:
        attempt = row.attempt
        if attempt is None or attempt.submitted_at is None:
            return "-"
        text = when(attempt.submitted_at)
        return f"{text} (time ended)" if attempt.auto_submitted else text

    def open_button(self, row: ResultRow) -> Any:
        attempt = row.attempt
        if attempt is None:
            return ""
        label = "Mark" if attempt.status == AttemptStatus.SUBMITTED else "Open"
        icon = "square-pen" if label == "Mark" else "eye"
        url = teacher_attempt_url(self.quiz, attempt)
        return IconButton(icon, f"{label}: {row.student}", url=url)


def answer_text(row: AnswerRow) -> str:
    """The chosen option of an MCQ question, or the written answer."""
    answer = row.answer
    if answer is None:
        return NO_ANSWER
    if row.item.question.kind == QuestionKind.MCQ:
        return answer.option.text if answer.option else NO_ANSWER
    return answer.text or NO_ANSWER


class AnswerTable(DataTable):
    """One attempt's answers in the student's order, with the right answer
    and the marks, on the teacher's attempt page."""

    empty_title = "This quiz has no questions."

    def __init__(self, rows: list[AnswerRow], **props):
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("number", "No.", lambda row: str(row.number)),
            Column("question", "Question", lambda row: row.item.question.text),
            Column("answer", "Answer", answer_text),
            Column(
                "right", "Right answer", lambda row: question_answer(row.item.question)
            ),
            Column("marks", "Marks", self.marks),
        ]

    def marks(self, row: AnswerRow) -> str:
        marks = row.answer.marks if row.answer else None
        return marks_text(marks, row.item.question.marks)
