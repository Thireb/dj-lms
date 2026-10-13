"""Lecture pages: admin All lectures / Add / Edit, teacher My lectures /
Create / Edit (roadmap 3.1, SPEC 3 and 4.5)."""

from __future__ import annotations

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
from apps.core import menus as menu_keys
from apps.core.query import id_param, search_param
from apps.core.responses import forbidden_response
from apps.core.roles import Role
from apps.lectures.forms import LectureForm
from apps.lectures.models import Lecture, LectureStatus
from apps.lectures.services import (
    SHOW_CHOICES,
    SHOW_UPCOMING,
    LectureDetails,
    SavedLecture,
    create_lecture,
    list_lectures,
    update_lecture,
)
from apps.lectures.times import combine_local, local_date, time_range
from apps.lectures.ui import LectureTable, TeacherLectureTable
from apps.people.models import TeacherProfile
from apps.ui.components.actions import Button
from apps.ui.components.block_stack import BlockStack
from apps.ui.components.data import EmptyState
from apps.ui.components.layout import LinkTabs
from apps.ui.components.nav import FilterBar, Pagination
from apps.ui.views.pages import FormPage, ListPage

PAGE_SIZE = 25
SHOW_KEYS = {key for key, _ in SHOW_CHOICES}
STATUS_OPTIONS = [("", "Any status"), *LectureStatus.choices]
EMPTY_TITLES = {
    "today": "No lectures today.",
    "upcoming": "No upcoming lectures.",
    "past": "No past lectures.",
    "all": "No lectures match these filters.",
}

# Service error keys, mapped onto form fields.
FORM_FIELDS = {
    "batch": "batch_subjects",
    "subjects": "batch_subjects",
    "starts_at": "start_time",
}


class AdminLectureMixin:
    portal = "admin"
    menu_key = menu_keys.ONLINE_LECTURES
    allowed_roles = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]
    table_class: type[LectureTable] = LectureTable
    create_label = "Add lecture"
    first_label = "Add your first lecture"

    def url(self, action: str, **kwargs: Any) -> str:
        return reverse(f"{self.portal}:lecture_{action}", kwargs=kwargs or None)

    def own_teacher(self) -> TeacherProfile | None:
        """The fixed teacher; admins choose one in the form."""
        return None


class TeacherLectureMixin(AdminLectureMixin):
    portal = "teacher"
    menu_key = None
    active_item = "lectures"
    allowed_roles = [Role.TEACHER]
    table_class = TeacherLectureTable
    create_label = "Create lecture"
    first_label = "Create your first lecture"

    def own_teacher(self) -> TeacherProfile | None:
        return TeacherProfile.objects.for_user(self.request.user).first()


# Lists


class LectureListPage(AdminLectureMixin, ListPage):
    title = "All lectures"
    filter_keys = ("teacher", "batch", "subject", "status")

    def get_actions(self) -> list[Any]:
        return [Button(self.create_label, url=self.url("create"), icon="plus")]

    def get_filters(self) -> dict[str, str]:
        filters = {
            key: search_param(self.request.GET.get(key)) for key in self.filter_keys
        }
        show = search_param(self.request.GET.get("show"))
        filters["show"] = show if show in SHOW_KEYS else SHOW_UPCOMING
        return filters

    def get_rows(self, filters: dict[str, str]) -> Any:
        return list_lectures(
            self.request.user,
            show=filters["show"],
            teacher_id=id_param(filters.get("teacher")),
            batch_id=id_param(filters["batch"]),
            subject_id=id_param(filters["subject"]),
            status=filters["status"],
        )

    def get_components(self) -> dict[str, Any]:
        filters = self.get_filters()
        page = Paginator(self.get_rows(filters), PAGE_SIZE).get_page(
            self.request.GET.get("page")
        )
        query = urlencode({key: value for key, value in filters.items() if value})
        return {
            "filters": BlockStack(
                blocks=[self.tabs(filters), FilterBar(self.filter_fields(filters))]
            ),
            "table": self.get_table(list(page.object_list), filters),
            "pagination": Pagination(page, query=query),
        }

    def tabs(self, filters: dict[str, str]) -> LinkTabs:
        kept = {k: v for k, v in filters.items() if v and k != "show"}
        return LinkTabs(
            [
                {
                    "id": key,
                    "label": label,
                    "url": "?" + urlencode({**kept, "show": key}),
                }
                for key, label in SHOW_CHOICES
            ],
            active=filters["show"],
            label="Lecture lists",
        )

    def options(self, rows: Any, empty_label: str) -> list[tuple[str, str]]:
        return [("", empty_label)] + [(str(row.pk), str(row)) for row in rows]

    def filter_fields(self, filters: dict[str, str]) -> list[dict[str, Any]]:
        user = self.request.user
        fields = [{"name": "show", "value": filters["show"], "hidden": True}]
        if "teacher" in self.filter_keys:
            teachers = (
                TeacherProfile.objects.for_user(user)
                .select_related("user")
                .order_by("user__first_name", "user__last_name", "pk")
            )
            fields.append(
                {
                    "name": "teacher",
                    "label": "Teacher",
                    "value": filters["teacher"],
                    "options": self.options(teachers, "Any teacher"),
                }
            )
        batches = Batch.objects.for_user(user).order_by("name")
        subjects = Subject.objects.for_user(user).order_by("name")
        return [
            *fields,
            {
                "name": "batch",
                "label": "Batch",
                "value": filters["batch"],
                "options": self.options(batches, "Any batch"),
            },
            {
                "name": "subject",
                "label": "Subject",
                "value": filters["subject"],
                "options": self.options(subjects, "Any subject"),
            },
            {
                "name": "status",
                "label": "Status",
                "value": filters["status"],
                "options": STATUS_OPTIONS,
            },
        ]

    def get_table(self, rows: list[Lecture], filters: dict[str, str]) -> Any:
        if not rows and not Lecture.objects.for_user(self.request.user).exists():
            return EmptyState(
                "No lectures yet.",
                icon="video",
                action=Button(self.first_label, url=self.url("create")),
            )
        return self.table_class(rows, empty_title=EMPTY_TITLES[filters["show"]])


class TeacherLectureListPage(TeacherLectureMixin, LectureListPage):
    title = "My lectures"
    filter_keys = ("batch", "subject", "status")


# Forms


class LectureFormPage(AdminLectureMixin, FormPage):
    form_class = LectureForm
    save_label = "Add lecture"
    success_message = "Lecture added."
    lecture: Lecture | None = None

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return self.load() or super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return self.load() or super().post(request, *args, **kwargs)

    def load(self) -> HttpResponse | None:
        """Runs after the access mixins. A teacher without a profile cannot
        own lectures, so they get 403."""
        self.teacher = self.own_teacher()
        if self.portal == "teacher" and self.teacher is None:
            return forbidden_response(self.request)
        return None

    def get_form_kwargs(self) -> dict[str, Any]:
        return {
            "user": self.request.user,
            "cancel_url": self.url("list"),
            "save_label": self.save_label,
            "lecture": self.lecture,
            "teacher": self.teacher,
            "teacher_param": self.request.GET.get("teacher"),
            "refresh_url": self.request.path,
            "initial": self.get_initial(),
        }

    def get_initial(self) -> dict[str, Any]:
        return {}

    def details(self, form: LectureForm) -> LectureDetails:
        data = form.cleaned_data
        batch, subjects = form.selection()
        return LectureDetails(
            title=data["title"],
            teacher=form.teacher(),
            batch=batch,
            subjects=subjects,
            starts_at=combine_local(data["date"], data["start_time"]),
            duration_minutes=data["duration_minutes"],
            delivery_mode=data["delivery_mode"],
            meeting_url=data["meeting_url"] or "",
            description=data["description"],
        )

    def form_valid(self, form: LectureForm) -> HttpResponse:
        try:
            saved = self.save(self.details(form))
        except ValidationError as error:
            for name, field_errors in error.message_dict.items():
                name = FORM_FIELDS.get(name, name)
                form.add_error(name if name in form.fields else None, field_errors)
            return self.form_invalid(form)
        messages.success(self.request, self.success_message)
        self.warn_batch_clashes(saved)
        return HttpResponseRedirect(self.url("list"))

    def warn_batch_clashes(self, saved: SavedLecture) -> None:
        for clash in saved.batch_clashes:
            when = time_range(clash.starts_at, clash.ends_at)
            messages.warning(
                self.request,
                f"{clash.batch.name} also has {clash.title} on "
                f"{local_date(clash.starts_at)}, {when}.",
            )

    def save(self, details: LectureDetails) -> SavedLecture:
        return create_lecture(self.get_institute(), details)


class LectureCreatePage(LectureFormPage):
    title = "Add lecture"


class LectureEditPage(LectureFormPage):
    title = "Edit lecture"
    save_label = "Save changes"
    success_message = "Lecture saved."

    def load(self) -> HttpResponse | None:
        denied = super().load()
        if denied is not None:
            return denied
        lectures = Lecture.objects.for_user(self.request.user).prefetch_related(
            "subjects"
        )
        self.lecture = get_object_or_404(lectures, pk=self.kwargs["pk"])
        return None

    def get_initial(self) -> dict[str, Any]:
        lecture = self.lecture
        local = timezone.localtime(lecture.starts_at)
        return {
            "title": lecture.title,
            "description": lecture.description,
            "teacher": lecture.teacher_id,
            "batch_subjects": [
                f"{lecture.batch_id}:{subject.pk}" for subject in lecture.subjects.all()
            ],
            "date": local.date(),
            "start_time": local.time().replace(second=0, microsecond=0),
            "duration_minutes": lecture.duration_minutes,
            "delivery_mode": lecture.delivery_mode,
            "meeting_url": lecture.meeting_url,
        }

    def save(self, details: LectureDetails) -> SavedLecture:
        return update_lecture(self.lecture, details)


class TeacherLectureCreatePage(TeacherLectureMixin, LectureCreatePage):
    title = "Create lecture"
    save_label = "Create lecture"
    active_item = "lecture_create"


class TeacherLectureEditPage(TeacherLectureMixin, LectureEditPage):
    pass
