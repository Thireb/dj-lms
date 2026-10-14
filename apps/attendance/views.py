"""Attendance pages (roadmap 4.1 to 4.3, SPEC 3 and 6.3)."""

from __future__ import annotations

from functools import cached_property
from typing import Any
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect

from apps.academics.models import Subject
from apps.attendance.forms import AttendanceForm
from apps.attendance.services import (
    by_month,
    by_subject,
    can_mark,
    roster,
    save_marks,
    student_records,
    student_subject_ids,
    summarize,
)
from apps.attendance.ui import AttendanceTable, SummaryTable, summary_cards
from apps.core import menus as menu_keys
from apps.core.query import id_param, search_param
from apps.core.roles import Role
from apps.lectures.ui import lecture_summary, lecture_when
from apps.lectures.views import (
    DATE_FIELD,
    PAGE_SIZE,
    LectureObjectMixin,
    TeacherLectureMixin,
    calendar_day,
)
from apps.people.models import StudentProfile
from apps.people.views import GuardianChildMixin
from apps.ui.components.block_stack import BlockStack
from apps.ui.components.data import EmptyState
from apps.ui.components.layout import LinkTabs
from apps.ui.components.nav import FilterBar, Pagination
from apps.ui.views.pages import FormPage, ListPage


class TakeAttendancePage(LectureObjectMixin, TeacherLectureMixin, FormPage):
    """Teacher "Take attendance" for one of their finished lectures."""

    title = "Take attendance"
    form_class = AttendanceForm

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return self.load() or super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return self.load() or super().post(request, *args, **kwargs)

    def load(self) -> HttpResponse | None:
        self.lecture = self.get_lecture()
        if can_mark(self.lecture):
            self.roster = roster(self.lecture)
            return None
        messages.error(self.request, "Attendance is taken only for a finished lecture.")
        return HttpResponseRedirect(self.detail_url())

    def detail_url(self) -> str:
        return self.url("detail", pk=self.lecture.pk)

    def get_subtitle(self) -> str:
        return f"{self.lecture.title}: {lecture_when(self.lecture)}. " + (
            lecture_summary(self.lecture)
        )

    def get_form_kwargs(self) -> dict[str, Any]:
        return {"roster": self.roster, "cancel_url": self.detail_url()}

    def get_components(self) -> dict[str, Any]:
        if not self.roster:
            return {
                "form": EmptyState(
                    "No students to mark.",
                    text="No student is enrolled in this batch and subject.",
                    icon="users",
                )
            }
        return super().get_components()

    def form_valid(self, form: AttendanceForm) -> HttpResponse:
        try:
            save_marks(self.lecture, form.marks(), marked_by=self.request.user)
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, f"Attendance saved for {self.lecture.title}.")
        return HttpResponseRedirect(self.detail_url())


# Read pages (roadmap 4.2, with the month and subject views of 4.3): My
# attendance, Class attendance, Student attendance history


VIEW_CLASSES = "classes"
VIEW_MONTHS = "months"
VIEW_SUBJECTS = "subjects"
VIEWS = {VIEW_CLASSES: "Classes", VIEW_MONTHS: "By month", VIEW_SUBJECTS: "By subject"}
NO_CLASSES = "No finished classes match these filters."


class StudentAttendancePage(ListPage):
    """Student "My attendance" (SPEC 3): the student's finished lectures with
    their marks, and the attendance % (SPEC 6.3)."""

    portal = "student"
    active_item = "attendance"
    allowed_roles = [Role.STUDENT]
    title = "My attendance"
    filter_keys = ("subject", "date_from", "date_to")
    no_student = EmptyState(
        "No student profile.", text="Contact the institute office.", icon="user"
    )

    def get_student(self) -> StudentProfile | None:
        return StudentProfile.objects.for_user(self.request.user).first()

    def get_filters(self) -> dict[str, str]:
        filters = {
            key: search_param(self.request.GET.get(key)) for key in self.filter_keys
        }
        for key in ("date_from", "date_to"):
            if calendar_day(filters[key]) is None:
                filters[key] = ""
        return filters

    def get_subtitle(self) -> str:
        student = self.student
        return f"Finished classes of {student}." if student else ""

    @cached_property
    def student(self) -> StudentProfile | None:
        return self.get_student()

    def get_components(self) -> dict[str, Any]:
        if self.student is None:
            return {"table": self.no_student}
        filters = self.get_filters()
        records = student_records(
            self.student,
            subject_id=id_param(filters.get("subject")),
            date_from=calendar_day(filters["date_from"]),
            date_to=calendar_day(filters["date_to"]),
        )
        view = search_param(self.request.GET.get("view"))
        view = view if view in VIEWS else VIEW_CLASSES
        components = {
            "filters": BlockStack(
                blocks=[
                    summary_cards(summarize(records)),
                    self.view_tabs(view, filters),
                    FilterBar(self.filter_fields(filters, view)),
                ]
            )
        }
        if view == VIEW_MONTHS:
            components["table"] = SummaryTable(
                by_month(records), label="Month", empty_title=NO_CLASSES
            )
        elif view == VIEW_SUBJECTS:
            subject_ids = student_subject_ids(self.student)
            components["table"] = SummaryTable(
                by_subject(records, subject_ids),
                label="Subject",
                empty_title=NO_CLASSES,
            )
        else:
            page = Paginator(records, PAGE_SIZE).get_page(self.request.GET.get("page"))
            query = urlencode(
                {"view": view} | {key: value for key, value in filters.items() if value}
            )
            components["table"] = AttendanceTable(list(page.object_list))
            components["pagination"] = Pagination(page, query=query)
        return components

    def view_tabs(self, view: str, filters: dict[str, str]) -> LinkTabs:
        kept = {key: value for key, value in filters.items() if value}
        return LinkTabs(
            [
                {
                    "id": key,
                    "label": label,
                    "url": "?" + urlencode(kept | {"view": key}),
                }
                for key, label in VIEWS.items()
            ],
            active=view,
            label="Attendance views",
        )

    def filter_fields(
        self, filters: dict[str, str], view: str = ""
    ) -> list[dict[str, Any]]:
        subjects = Subject.objects.for_user(self.request.user).filter(
            student_links__student=self.student
        )
        return [
            {"name": "view", "value": view, "hidden": True},
            {
                "name": "subject",
                "label": "Subject",
                "value": filters["subject"],
                "options": [("", "Any subject")]
                + [(str(row.pk), row.name) for row in subjects.distinct()],
            },
            {"name": "date_from", "label": "From", "value": filters["date_from"]}
            | DATE_FIELD,
            {"name": "date_to", "label": "To", "value": filters["date_to"]}
            | DATE_FIELD,
        ]


class GuardianAttendancePage(GuardianChildMixin, StudentAttendancePage):
    """Guardian "Class attendance": the same page for the chosen child."""

    portal = "guardian"
    allowed_roles = [Role.GUARDIAN]
    title = "Class attendance"
    no_student = EmptyState(
        "No children are linked to this account yet.",
        text="Contact the institute office.",
        icon="graduation-cap",
    )

    def get_student(self) -> StudentProfile | None:
        return self.child


class AdminStudentAttendancePage(StudentAttendancePage):
    """Admin "Student attendance history" (People menu): one student at a
    time, chosen in the filter or from All students."""

    portal = "admin"
    menu_key = menu_keys.PEOPLE
    active_item = None
    allowed_roles = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]
    title = "Student attendance history"
    filter_keys = ("student", "subject", "date_from", "date_to")

    @cached_property
    def students(self) -> list[StudentProfile]:
        return list(
            StudentProfile.objects.for_user(self.request.user)
            .select_related("user")
            .order_by("user__first_name", "user__last_name", "pk")
        )

    def get_student(self) -> StudentProfile | None:
        wanted = id_param(search_param(self.request.GET.get("student")))
        return next((row for row in self.students if row.pk == wanted), None)

    def get_components(self) -> dict[str, Any]:
        if self.student is not None:
            return super().get_components()
        filters = self.get_filters()
        return {
            "filters": FilterBar(self.filter_fields(filters)),
            "table": EmptyState(
                "Choose a student.",
                text="Their finished classes and attendance show here.",
                icon="clipboard-list",
            ),
        }

    def filter_fields(
        self, filters: dict[str, str], view: str = ""
    ) -> list[dict[str, Any]]:
        student = {
            "name": "student",
            "label": "Student",
            "value": filters["student"],
            "options": [("", "Choose a student")]
            + [(str(row.pk), f"{row} ({row.student_code})") for row in self.students],
        }
        if self.student is None:
            return [student]
        return [student, *super().filter_fields(filters, view)]
