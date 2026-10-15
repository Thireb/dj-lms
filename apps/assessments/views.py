"""Assignment pages (roadmap 5.1, SPEC 3 and 4.16): teacher Assignments,
Add / Edit, the answers and the grade page; student Assignments and the
assignment page with the answer form. Teacher "Question bank" (roadmap
5.2): list, Add, Edit and Delete. Teacher "Quizzes and exams" set-up
(roadmap 5.3): list, Add, Edit, the quiz page, Add questions, Publish."""

from __future__ import annotations

from functools import cached_property
from typing import Any
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import Batch, Subject
from apps.assessments.forms import (
    AddQuestionsForm,
    AnswerForm,
    AssignmentForm,
    GradeForm,
    QuestionForm,
    QuizForm,
)
from apps.assessments.models import (
    Assignment,
    Question,
    QuestionKind,
    Quiz,
    QuizKind,
    QuizQuestion,
    QuizStatus,
    Submission,
    SubmissionStatus,
)
from apps.assessments.services import (
    OPENED_MESSAGE,
    AssignmentDetails,
    QuestionDetails,
    QuizDetails,
    add_questions,
    assignment_counts,
    bank_choices,
    create_assignment,
    create_quiz,
    delete_question,
    grade_submission,
    has_opened,
    is_expected,
    is_open,
    list_questions,
    list_quizzes,
    marks_text,
    publish_quiz,
    quiz_items,
    quiz_status,
    remove_question,
    save_question,
    student_assignments,
    submission_rows,
    submission_status,
    submit_answer,
    unpublish_quiz,
    update_assignment,
    update_quiz,
)
from apps.assessments.ui import (
    QuestionTable,
    QuizItemTable,
    StudentAssignmentTable,
    SubmissionTable,
    TeacherAssignmentTable,
    TeacherQuizTable,
    assignment_detail_rows,
    form_card,
    quiz_detail_rows,
    quiz_url,
    submission_badge,
    when,
)
from apps.core.query import id_param, search_param
from apps.core.responses import forbidden_response
from apps.core.roles import Role
from apps.people.models import StudentProfile, TeacherProfile
from apps.ui.components.actions import Button, PostButton
from apps.ui.components.block_stack import ButtonRow
from apps.ui.components.data import DetailList, EmptyState, TextBlock
from apps.ui.components.layout import SectionCard
from apps.ui.components.nav import FilterBar, Pagination
from apps.ui.views.pages import DetailPage, FormPage, ListPage, PortalPageView

PAGE_SIZE = 25
STATUS_OPTIONS = [("", "Any status"), *SubmissionStatus.choices]

# Service error keys, mapped onto form fields.
FORM_FIELDS = {
    "batch": "batch_subject",
    "subject": "batch_subject",
    "due_at": "due_time",
}


def add_errors(form: Any, error: ValidationError, names: dict) -> None:
    """Put a service error on the form: a field error on its field (``names``
    maps service keys to form fields), any other on the whole form."""
    if not hasattr(error, "error_dict"):
        form.add_error(None, error)
        return
    for name, field_errors in error.message_dict.items():
        name = names.get(name, name)
        form.add_error(name if name in form.fields else None, field_errors)


def _options(rows: Any, empty_label: str) -> list[tuple[str, str]]:
    return [("", empty_label)] + [(str(row.pk), str(row)) for row in rows]


# Teacher


class TeacherAssignmentMixin:
    portal = "teacher"
    active_item = "assignments"
    allowed_roles = [Role.TEACHER]

    def url(self, action: str, **kwargs: Any) -> str:
        return reverse(f"teacher:assignment_{action}", kwargs=kwargs or None)

    def own_teacher(self) -> TeacherProfile | None:
        return TeacherProfile.objects.for_user(self.request.user).first()

    def get_assignment(self) -> Assignment:
        """The assignment from the URL, through ``for_user`` (404 when not
        the teacher's own)."""
        rows = Assignment.objects.for_user(self.request.user).select_related(
            "teacher__user", "batch", "subject"
        )
        return get_object_or_404(rows, pk=self.kwargs["pk"])


class TeacherAssignmentListPage(TeacherAssignmentMixin, ListPage):
    title = "Assignments"
    filter_keys = ("batch", "subject")

    def get_actions(self) -> list[Any]:
        return [Button("Add assignment", url=self.url("create"), icon="plus")]

    def get_components(self) -> dict[str, Any]:
        mine = Assignment.objects.for_user(self.request.user)
        if not mine.exists():
            return {
                "table": EmptyState(
                    "No assignments yet.",
                    text="Students see an assignment as soon as you add it.",
                    icon="list-checks",
                    action=Button("Add your first assignment", url=self.url("create")),
                )
            }
        filters = {
            key: search_param(self.request.GET.get(key)) for key in self.filter_keys
        }
        rows = mine.select_related("batch", "subject")
        for key in self.filter_keys:
            wanted = id_param(filters[key])
            if wanted is not None:
                rows = rows.filter(**{f"{key}_id": wanted})
        page = Paginator(rows, PAGE_SIZE).get_page(self.request.GET.get("page"))
        assignments = list(page.object_list)
        query = urlencode({key: value for key, value in filters.items() if value})
        return {
            "filters": FilterBar(self.filter_fields(filters)),
            "table": TeacherAssignmentTable(
                assignments, counts=assignment_counts(assignments)
            ),
            "pagination": Pagination(page, query=query),
        }

    def filter_fields(self, filters: dict[str, str]) -> list[dict[str, Any]]:
        user = self.request.user
        batches = Batch.objects.for_user(user).order_by("name")
        subjects = Subject.objects.for_user(user).order_by("name")
        return [
            {
                "name": "batch",
                "label": "Batch",
                "value": filters["batch"],
                "options": _options(batches, "Any batch"),
            },
            {
                "name": "subject",
                "label": "Subject",
                "value": filters["subject"],
                "options": _options(subjects, "Any subject"),
            },
        ]


class AssignmentFormPage(TeacherAssignmentMixin, FormPage):
    title = "Add assignment"
    form_class = AssignmentForm
    save_label = "Add assignment"
    success_message = "Assignment added. Students can see it now."
    assignment: Assignment | None = None

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return self.load() or super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return self.load() or super().post(request, *args, **kwargs)

    def load(self) -> HttpResponse | None:
        """Runs after the access mixins. A teacher without a profile cannot
        own assignments, so they get 403."""
        self.teacher = self.own_teacher()
        if self.teacher is None:
            return forbidden_response(self.request)
        return None

    def get_form_kwargs(self) -> dict[str, Any]:
        return {
            "user": self.request.user,
            "teacher": self.teacher,
            "cancel_url": self.url("list"),
            "save_label": self.save_label,
            "assignment": self.assignment,
            "initial": self.get_initial(),
        }

    def get_initial(self) -> dict[str, Any]:
        return {}

    def details(self, form: AssignmentForm) -> AssignmentDetails:
        data = form.cleaned_data
        batch, subject = form.selection()
        return AssignmentDetails(
            title=data["title"],
            instructions=data["instructions"],
            teacher=self.teacher,
            batch=batch,
            subject=subject,
            total_marks=data["total_marks"],
            due_at=data["due_at"],
        )

    def form_valid(self, form: AssignmentForm) -> HttpResponse:
        try:
            saved = self.save(self.details(form))
        except ValidationError as error:
            for name, field_errors in error.message_dict.items():
                name = FORM_FIELDS.get(name, name)
                form.add_error(name if name in form.fields else None, field_errors)
            return self.form_invalid(form)
        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.url("detail", pk=saved.pk))

    def save(self, details: AssignmentDetails) -> Assignment:
        return create_assignment(self.get_institute(), details)


class AssignmentCreatePage(AssignmentFormPage):
    pass


class AssignmentEditPage(AssignmentFormPage):
    title = "Edit assignment"
    save_label = "Save changes"
    success_message = "Assignment saved."

    def load(self) -> HttpResponse | None:
        denied = super().load()
        if denied is not None:
            return denied
        self.assignment = self.get_assignment()
        return None

    def get_subtitle(self) -> str:
        return (
            "Students see the changes at once. The batch and subject stay the "
            "same after the first answer."
        )

    def get_initial(self) -> dict[str, Any]:
        assignment = self.assignment
        local = timezone.localtime(assignment.due_at)
        return {
            "title": assignment.title,
            "instructions": assignment.instructions,
            "batch_subject": f"{assignment.batch_id}:{assignment.subject_id}",
            "total_marks": assignment.total_marks,
            "due_date": local.date(),
            "due_time": local.time().replace(second=0, microsecond=0),
        }

    def save(self, details: AssignmentDetails) -> Assignment:
        return update_assignment(self.assignment, details)


class TeacherAssignmentDetailPage(TeacherAssignmentMixin, DetailPage):
    """The assignment, and every expected student's answer to grade."""

    title = "Assignment"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.assignment = self.get_assignment()
        self.title = self.assignment.title
        return super().get(request, *args, **kwargs)

    def get_subtitle(self) -> str:
        state = "Open" if is_open(self.assignment) else "Closed"
        return f"{state}. Due {when(self.assignment.due_at)}."

    def get_actions(self) -> list[Any]:
        url = self.url("edit", pk=self.assignment.pk)
        return [Button("Edit", variant="secondary", url=url, icon="square-pen")]

    def get_primary_cards(self) -> list[Any]:
        assignment = self.assignment
        return [
            SectionCard(
                title="Instructions",
                icon="file-text",
                body=TextBlock(assignment.instructions),
            ),
            SectionCard(
                title="Answers",
                icon="list-checks",
                body=SubmissionTable(
                    submission_rows(assignment), assignment=assignment
                ),
            ),
        ]

    def get_sidebar_cards(self) -> list[Any]:
        rows = assignment_detail_rows(self.assignment, show_teacher=False)
        return [SectionCard(title="Details", icon="list", body=DetailList(rows))]


class GradePage(TeacherAssignmentMixin, DetailPage):
    """One student's answer with the marks and feedback form."""

    title = "Grade answer"

    def load(self) -> None:
        self.assignment = self.get_assignment()
        rows = Submission.objects.for_user(self.request.user).select_related(
            "student__user"
        )
        self.submission = get_object_or_404(
            rows, pk=self.kwargs["submission_pk"], assignment=self.assignment
        )
        self.title = f"Grade: {self.submission.student}"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.load()
        self.form = self.make_form()
        return super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.load()
        self.form = self.make_form(request.POST)
        if self.form.is_valid():
            data = self.form.cleaned_data
            try:
                grade_submission(
                    self.submission,
                    data["marks"],
                    data["feedback"],
                    graded_by=request.user,
                )
            except ValidationError as error:
                for name, field_errors in error.message_dict.items():
                    target = name if name in self.form.fields else None
                    self.form.add_error(target, field_errors)
            else:
                messages.success(request, f"Grade saved for {self.submission.student}.")
                return HttpResponseRedirect(self.detail_url())
        return self.render_to_response(self.get_context_data())

    def detail_url(self) -> str:
        return self.url("detail", pk=self.assignment.pk)

    def make_form(self, data: Any = None) -> GradeForm:
        submission = self.submission
        initial = {}
        if submission.is_graded:
            initial = {"marks": submission.marks, "feedback": submission.feedback}
        return GradeForm(
            data,
            total_marks=self.assignment.total_marks,
            cancel_url=self.detail_url(),
            initial=initial,
        )

    def get_subtitle(self) -> str:
        return f"{self.assignment.title}: {self.assignment.total_marks} marks."

    def get_primary_cards(self) -> list[Any]:
        return [
            SectionCard(
                title="Answer",
                icon="file-text",
                body=TextBlock(self.submission.answer),
            ),
            form_card("Marks and feedback", self.form, self.request.path, "square-pen"),
        ]

    def get_sidebar_cards(self) -> list[Any]:
        submission = self.submission
        status = submission_status(self.assignment, submission, timezone.now())
        rows = [
            ("Student", str(submission.student)),
            ("Student ID", submission.student.student_code),
            ("Status", submission_badge(status)),
            ("Submitted on", when(submission.submitted_at)),
            ("Graded on", when(submission.graded_at)),
        ]
        return [SectionCard(title="Details", icon="list", body=DetailList(rows))]


# Student


class StudentAssignmentMixin:
    portal = "student"
    active_item = "assignments"
    allowed_roles = [Role.STUDENT]
    no_student = EmptyState(
        "No student profile.", text="Contact the institute office.", icon="user"
    )

    @cached_property
    def student(self) -> StudentProfile | None:
        return StudentProfile.objects.for_user(self.request.user).first()


class StudentAssignmentListPage(StudentAssignmentMixin, ListPage):
    """Student "Assignments" (SPEC 3), with the pending, submitted, graded
    and missed filter (FEATURES 7)."""

    title = "Assignments"
    filter_keys = ("status", "subject")

    def get_components(self) -> dict[str, Any]:
        if self.student is None:
            return {"table": self.no_student}
        filters = {
            key: search_param(self.request.GET.get(key)) for key in self.filter_keys
        }
        if filters["status"] not in SubmissionStatus.values:
            filters["status"] = ""
        rows = student_assignments(
            self.student,
            subject_id=id_param(filters["subject"]),
            status=filters["status"],
        )
        page = Paginator(rows, PAGE_SIZE).get_page(self.request.GET.get("page"))
        query = urlencode({key: value for key, value in filters.items() if value})
        return {
            "filters": FilterBar(self.filter_fields(filters)),
            "table": StudentAssignmentTable(list(page.object_list)),
            "pagination": Pagination(page, query=query),
        }

    def filter_fields(self, filters: dict[str, str]) -> list[dict[str, Any]]:
        subjects = Subject.objects.for_user(self.request.user).filter(
            student_links__student=self.student
        )
        return [
            {
                "name": "status",
                "label": "Status",
                "value": filters["status"],
                "options": STATUS_OPTIONS,
            },
            {
                "name": "subject",
                "label": "Subject",
                "value": filters["subject"],
                "options": _options(
                    subjects.distinct().order_by("name"), "Any subject"
                ),
            },
        ]


class StudentAssignmentPage(StudentAssignmentMixin, DetailPage):
    """One assignment: the instructions, the answer form until the due time,
    then the marks and feedback once graded."""

    title = "Assignment"

    def load(self) -> HttpResponse | None:
        if self.student is None:
            return forbidden_response(self.request)
        rows = Assignment.objects.for_user(self.request.user).select_related(
            "teacher__user", "batch", "subject"
        )
        self.assignment = get_object_or_404(rows, pk=self.kwargs["pk"])
        if not is_expected(self.assignment, self.student):
            # Enrolled after the due time: the assignment is not theirs.
            return HttpResponseRedirect(reverse("student:assignment_list"))
        self.title = self.assignment.title
        self.submission = Submission.objects.filter(
            assignment=self.assignment, student=self.student
        ).first()
        self.now = timezone.now()
        self.form = self.make_form() if self.can_answer() else None
        return None

    def can_answer(self) -> bool:
        graded = self.submission is not None and self.submission.is_graded
        return is_open(self.assignment, self.now) and not graded

    def make_form(self, data: Any = None) -> AnswerForm:
        answered = self.submission is not None
        return AnswerForm(
            data,
            save_label="Save answer" if answered else "Submit answer",
            cancel_url=reverse("student:assignment_list"),
            initial={"answer": self.submission.answer} if answered else {},
        )

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return self.load() or super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        refused = self.load()
        if refused is not None:
            return refused
        if self.form is None:
            messages.error(request, "This assignment no longer takes answers.")
            return HttpResponseRedirect(request.path)
        self.form = self.make_form(request.POST)
        if self.form.is_valid():
            try:
                submit_answer(
                    self.assignment, self.student, self.form.cleaned_data["answer"]
                )
            except ValidationError as error:
                if hasattr(error, "error_dict"):
                    for name, field_errors in error.message_dict.items():
                        self.form.add_error(
                            name if name in self.form.fields else None, field_errors
                        )
                else:
                    self.form.add_error(None, error)
            else:
                messages.success(request, "Answer saved. Your teacher can see it now.")
                return HttpResponseRedirect(request.path)
        return self.render_to_response(self.get_context_data())

    @property
    def status(self) -> str:
        return submission_status(self.assignment, self.submission, self.now)

    def get_subtitle(self) -> str:
        return f"{self.assignment.subject.name}. Due {when(self.assignment.due_at)}."

    def get_primary_cards(self) -> list[Any]:
        cards = [
            SectionCard(
                title="Instructions",
                icon="file-text",
                body=TextBlock(self.assignment.instructions),
            )
        ]
        submission = self.submission
        if submission is not None and submission.is_graded:
            cards.append(self.grade_card(submission))
        if self.form is not None:
            title = "Your answer" if submission is None else "Change your answer"
            cards.append(form_card(title, self.form, self.request.path, "square-pen"))
        elif submission is not None:
            cards.append(
                SectionCard(
                    title="Your answer",
                    icon="file-text",
                    body=TextBlock(submission.answer),
                )
            )
        else:
            cards.append(
                SectionCard(
                    title="Your answer",
                    icon="file-text",
                    body=EmptyState(
                        "No answer was sent.",
                        text="The due time has passed.",
                        icon="clock",
                        framed=False,
                    ),
                )
            )
        return cards

    def grade_card(self, submission: Submission) -> SectionCard:
        rows = [
            ("Marks", marks_text(submission.marks, self.assignment.total_marks)),
            ("Feedback", TextBlock(submission.feedback, empty_text="No feedback.")),
        ]
        return SectionCard(title="Grade", icon="check", body=DetailList(rows))

    def get_sidebar_cards(self) -> list[Any]:
        rows = [
            ("Status", submission_badge(self.status)),
            *assignment_detail_rows(self.assignment, show_teacher=True),
            (
                "Submitted on",
                when(self.submission.submitted_at) if self.submission else "",
            ),
        ]
        return [SectionCard(title="Details", icon="list", body=DetailList(rows))]


# Question bank (roadmap 5.2)

KIND_OPTIONS = [("", "Any type"), *QuestionKind.choices]

# Service error keys, mapped onto form fields.
QUESTION_FIELDS = {"options": "option_1", "teacher": None}


class QuestionMixin(TeacherAssignmentMixin):
    active_item = "questions"

    def url(self, action: str, **kwargs: Any) -> str:
        return reverse(f"teacher:question_{action}", kwargs=kwargs or None)

    def get_question(self) -> Question:
        """The question from the URL, through ``for_user`` (404 when not the
        teacher's own)."""
        rows = Question.objects.for_user(self.request.user).prefetch_related("options")
        return get_object_or_404(rows, pk=self.kwargs["pk"])


class QuestionListPage(QuestionMixin, ListPage):
    title = "Question bank"
    filter_keys = ("q", "subject", "kind")

    def get_subtitle(self) -> str:
        return "Your saved questions. Quizzes and exams take them from here."

    def get_actions(self) -> list[Any]:
        return [Button("Add question", url=self.url("create"), icon="plus")]

    def get_components(self) -> dict[str, Any]:
        user = self.request.user
        if not Question.objects.for_user(user).exists():
            return {
                "table": EmptyState(
                    "No questions yet.",
                    text="Save MCQ and short answer questions to use in quizzes.",
                    icon="square-pen",
                    action=Button("Add your first question", url=self.url("create")),
                )
            }
        filters = {
            key: search_param(self.request.GET.get(key)) for key in self.filter_keys
        }
        if filters["kind"] not in QuestionKind.values:
            filters["kind"] = ""
        rows = list_questions(
            user,
            subject_id=id_param(filters["subject"]),
            kind=filters["kind"],
            search=filters["q"],
        )
        page = Paginator(rows, PAGE_SIZE).get_page(self.request.GET.get("page"))
        query = urlencode({key: value for key, value in filters.items() if value})
        return {
            "filters": FilterBar(self.filter_fields(filters)),
            "table": QuestionTable(list(page.object_list)),
            "pagination": Pagination(page, query=query),
        }

    def filter_fields(self, filters: dict[str, str]) -> list[dict[str, Any]]:
        subjects = Subject.objects.for_user(self.request.user).order_by("name")
        return [
            {
                "name": "q",
                "label": "Search questions",
                "value": filters["q"],
                "placeholder": "Words in the question",
            },
            {
                "name": "subject",
                "label": "Subject",
                "value": filters["subject"],
                "options": _options(subjects, "Any subject"),
            },
            {
                "name": "kind",
                "label": "Type",
                "value": filters["kind"],
                "options": KIND_OPTIONS,
            },
        ]


class QuestionFormPage(QuestionMixin, FormPage):
    title = "Add question"
    form_class = QuestionForm
    save_label = "Add question"
    success_message = "Question added to your bank."
    question: Question | None = None

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return self.load() or super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return self.load() or super().post(request, *args, **kwargs)

    def load(self) -> HttpResponse | None:
        """Runs after the access mixins. A teacher without a profile has no
        bank, so they get 403."""
        self.teacher = self.own_teacher()
        if self.teacher is None:
            return forbidden_response(self.request)
        return None

    def get_form_kwargs(self) -> dict[str, Any]:
        return {
            "user": self.request.user,
            "teacher": self.teacher,
            "cancel_url": self.url("list"),
            "save_label": self.save_label,
            "question": self.question,
            "initial": self.get_initial(),
        }

    def get_initial(self) -> dict[str, Any]:
        return {}

    def form_valid(self, form: QuestionForm) -> HttpResponse:
        data = form.cleaned_data
        details = QuestionDetails(
            teacher=self.teacher,
            subject=data["subject"],
            kind=data["kind"],
            text=data["text"],
            marks=data["marks"],
            explanation=data["explanation"],
            options=data["options"],
            correct=data["correct_index"],
        )
        try:
            saved = save_question(self.get_institute(), details, self.question)
        except ValidationError as error:
            add_errors(form, error, QUESTION_FIELDS)
            return self.form_invalid(form)
        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.done_url(saved))

    def done_url(self, question: Question) -> str:
        return self.url("list")


class QuestionCreatePage(QuestionFormPage):
    """``?quiz=<pk>`` adds the new question to that quiz too (SPEC 4.16:
    "pick from bank or add new")."""

    @cached_property
    def quiz(self) -> Quiz | None:
        wanted = id_param(search_param(self.request.GET.get("quiz")))
        if wanted is None:
            return None
        return Quiz.objects.for_user(self.request.user).filter(pk=wanted).first()

    def get_subtitle(self) -> str:
        if self.quiz is None:
            return ""
        return f"It is saved in your bank and added to {self.quiz.title}."

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        if self.quiz is not None:
            kwargs["cancel_url"] = quiz_url("detail", self.quiz)
        return kwargs

    def get_initial(self) -> dict[str, Any]:
        return {"subject": self.quiz.subject_id} if self.quiz else {}

    def done_url(self, question: Question) -> str:
        if self.quiz is None:
            return self.url("list")
        try:
            add_questions(self.quiz, [question])
        except ValidationError as error:
            messages.warning(
                self.request, f"Saved in your bank only. {' '.join(error.messages)}"
            )
        return quiz_url("detail", self.quiz)


class QuestionEditPage(QuestionFormPage):
    title = "Edit question"
    save_label = "Save changes"
    success_message = "Question saved."

    def load(self) -> HttpResponse | None:
        denied = super().load()
        if denied is not None:
            return denied
        self.question = self.get_question()
        return None

    def get_initial(self) -> dict[str, Any]:
        return QuestionForm.initial_for(self.question)


class QuestionDeleteView(QuestionMixin, PortalPageView):
    """POST only: delete one of the teacher's questions (confirm dialog on
    the list)."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        try:
            delete_question(self.get_question())
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, "Question deleted.")
        return HttpResponseRedirect(self.url("list"))


# Quizzes and exams: set-up (roadmap 5.3)

QUIZ_STATUS_OPTIONS = [("", "Any status"), *QuizStatus.choices]
QUIZ_KIND_OPTIONS = [("", "Any type"), *QuizKind.choices]
QUIZ_FIELDS = {
    "batch": "batch_subject",
    "subject": "batch_subject",
    "opens_at": "opens_time",
}


class QuizMixin(TeacherAssignmentMixin):
    active_item = "quizzes"

    def url(self, action: str, **kwargs: Any) -> str:
        return reverse(f"teacher:quiz_{action}", kwargs=kwargs or None)

    def get_quiz(self) -> Quiz:
        """The quiz from the URL, through ``for_user`` (404 when not the
        teacher's own)."""
        rows = Quiz.objects.for_user(self.request.user).select_related(
            "batch", "subject"
        )
        return get_object_or_404(rows, pk=self.kwargs["pk"])


class TeacherQuizListPage(QuizMixin, ListPage):
    title = "Quizzes and exams"
    filter_keys = ("kind", "status")

    def get_actions(self) -> list[Any]:
        return [Button("Add quiz", url=self.url("create"), icon="plus")]

    def get_components(self) -> dict[str, Any]:
        user = self.request.user
        if not Quiz.objects.for_user(user).exists():
            return {
                "table": EmptyState(
                    "No quizzes yet.",
                    text="Add a quiz, pick questions from your bank, then publish.",
                    icon="square-pen",
                    action=Button("Add your first quiz", url=self.url("create")),
                )
            }
        filters = {
            key: search_param(self.request.GET.get(key)) for key in self.filter_keys
        }
        if filters["kind"] not in QuizKind.values:
            filters["kind"] = ""
        if filters["status"] not in QuizStatus.values:
            filters["status"] = ""
        rows = list_quizzes(user, kind=filters["kind"], status=filters["status"])
        page = Paginator(rows, PAGE_SIZE).get_page(self.request.GET.get("page"))
        query = urlencode({key: value for key, value in filters.items() if value})
        return {
            "filters": FilterBar(
                [
                    {
                        "name": "kind",
                        "label": "Type",
                        "value": filters["kind"],
                        "options": QUIZ_KIND_OPTIONS,
                    },
                    {
                        "name": "status",
                        "label": "Status",
                        "value": filters["status"],
                        "options": QUIZ_STATUS_OPTIONS,
                    },
                ]
            ),
            "table": TeacherQuizTable(list(page.object_list)),
            "pagination": Pagination(page, query=query),
        }


class QuizFormPage(QuizMixin, FormPage):
    title = "Add quiz"
    form_class = QuizForm
    save_label = "Add quiz"
    success_message = "Quiz added as a draft. Add questions, then publish it."
    quiz: Quiz | None = None

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return self.load() or super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return self.load() or super().post(request, *args, **kwargs)

    def load(self) -> HttpResponse | None:
        self.teacher = self.own_teacher()
        if self.teacher is None:
            return forbidden_response(self.request)
        return None

    def get_form_kwargs(self) -> dict[str, Any]:
        return {
            "user": self.request.user,
            "teacher": self.teacher,
            "cancel_url": self.url("list"),
            "save_label": self.save_label,
            "quiz": self.quiz,
            "initial": self.get_initial(),
        }

    def get_initial(self) -> dict[str, Any]:
        return {}

    def form_valid(self, form: QuizForm) -> HttpResponse:
        data = form.cleaned_data
        batch, subject = form.selection()
        details = QuizDetails(
            title=data["title"],
            kind=data["kind"],
            teacher=self.teacher,
            batch=batch,
            subject=subject,
            opens_at=data["opens_at"],
            duration_minutes=data["duration_minutes"],
            pass_marks=data["pass_marks"],
            shuffle_questions=data["shuffle_questions"],
            require_full_screen=data["require_full_screen"],
            flag_tab_leaving=data["flag_tab_leaving"],
        )
        try:
            saved = self.save(details)
        except ValidationError as error:
            add_errors(form, error, QUIZ_FIELDS)
            return self.form_invalid(form)
        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.url("detail", pk=saved.pk))

    def save(self, details: QuizDetails) -> Quiz:
        return create_quiz(self.get_institute(), details)


class QuizCreatePage(QuizFormPage):
    pass


class QuizEditPage(QuizFormPage):
    title = "Edit quiz"
    save_label = "Save changes"
    success_message = "Quiz saved."

    def load(self) -> HttpResponse | None:
        denied = super().load()
        if denied is not None:
            return denied
        self.quiz = self.get_quiz()
        if has_opened(self.quiz):
            messages.error(self.request, OPENED_MESSAGE)
            return HttpResponseRedirect(self.url("detail", pk=self.quiz.pk))
        return None

    def get_initial(self) -> dict[str, Any]:
        return QuizForm.initial_for(self.quiz)

    def save(self, details: QuizDetails) -> Quiz:
        return update_quiz(self.quiz, details)


class TeacherQuizDetailPage(QuizMixin, DetailPage):
    """The quiz settings and its questions, with Add questions, Publish and
    Back to draft until it opens."""

    title = "Quiz"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.quiz = self.get_quiz()
        self.title = self.quiz.title
        self.now = timezone.now()
        self.items = quiz_items(self.quiz)
        self.editable = not has_opened(self.quiz, self.now)
        return super().get(request, *args, **kwargs)

    def get_subtitle(self) -> str:
        quiz = self.quiz
        status = QuizStatus(quiz_status(quiz, self.now))
        if status == QuizStatus.DRAFT:
            return "Draft: students do not see it until you publish it."
        if status == QuizStatus.SCHEDULED:
            return f"Students see it now. It opens {when(quiz.opens_at)}."
        return f"{status.label}. It closes {when(quiz.closes_at)}."

    def get_actions(self) -> list[Any]:
        if not self.editable:
            return []
        quiz = self.quiz
        actions: list[Any] = []
        if quiz.is_published:
            actions.append(
                PostButton(
                    "Back to draft",
                    self.url("unpublish", pk=quiz.pk),
                    variant="secondary",
                    icon="eye-off",
                )
            )
        else:
            actions.append(
                PostButton("Publish", self.url("publish", pk=quiz.pk), icon="send")
            )
        actions.append(
            Button(
                "Edit",
                variant="secondary",
                url=self.url("edit", pk=quiz.pk),
                icon="square-pen",
            )
        )
        return actions

    def get_primary_cards(self) -> list[Any]:
        quiz = self.quiz
        card = SectionCard(
            title="Questions",
            icon="list-checks",
            body=QuizItemTable(self.items, editable=self.editable),
        )
        if not self.editable:
            return [card]
        buttons = ButtonRow(
            items=[
                Button(
                    "Add from bank",
                    url=self.url("add_questions", pk=quiz.pk),
                    icon="plus",
                ),
                Button(
                    "New question",
                    variant="secondary",
                    url=reverse("teacher:question_create") + f"?quiz={quiz.pk}",
                    icon="file-plus",
                ),
            ]
        )
        return [buttons, card]

    def get_sidebar_cards(self) -> list[Any]:
        total = sum(item.question.marks for item in self.items)
        rows = quiz_detail_rows(self.quiz, total=total, now=self.now)
        return [SectionCard(title="Details", icon="list", body=DetailList(rows))]


class QuizAddQuestionsPage(QuizMixin, FormPage):
    title = "Add questions"
    form_class = AddQuestionsForm

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return self.load() or super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return self.load() or super().post(request, *args, **kwargs)

    def load(self) -> HttpResponse | None:
        self.quiz = self.get_quiz()
        if has_opened(self.quiz):
            messages.error(self.request, OPENED_MESSAGE)
            return HttpResponseRedirect(self.detail_url())
        return None

    def detail_url(self) -> str:
        return self.url("detail", pk=self.quiz.pk)

    def get_subtitle(self) -> str:
        return f"{self.quiz.title}: your {self.quiz.subject.name} questions."

    def get_form_kwargs(self) -> dict[str, Any]:
        return {
            "choices": list(bank_choices(self.quiz)),
            "cancel_url": self.detail_url(),
        }

    def form_valid(self, form: AddQuestionsForm) -> HttpResponse:
        try:
            added = add_questions(self.quiz, form.chosen())
        except ValidationError as error:
            add_errors(form, error, {})
            return self.form_invalid(form)
        noun = "question" if added == 1 else "questions"
        messages.success(self.request, f"{added} {noun} added.")
        return HttpResponseRedirect(self.detail_url())


class QuizActionView(QuizMixin, PortalPageView):
    """POST only: change a quiz, then go back to its page."""

    http_method_names = ["post"]
    success_message = ""

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        quiz = self.get_quiz()
        try:
            self.change(quiz)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, self.success_message)
        return HttpResponseRedirect(self.url("detail", pk=quiz.pk))

    def change(self, quiz: Quiz) -> None:
        raise NotImplementedError


class QuizPublishView(QuizActionView):
    success_message = "Quiz published. Students see it now."

    def change(self, quiz: Quiz) -> None:
        publish_quiz(quiz)


class QuizUnpublishView(QuizActionView):
    success_message = "Quiz moved back to draft. Students no longer see it."

    def change(self, quiz: Quiz) -> None:
        unpublish_quiz(quiz)


class QuizRemoveQuestionView(QuizActionView):
    success_message = "Question removed from the quiz. It stays in your bank."

    def change(self, quiz: Quiz) -> None:
        item = get_object_or_404(
            QuizQuestion.objects.filter(quiz=quiz), pk=self.kwargs["item_pk"]
        )
        remove_question(quiz, item)
