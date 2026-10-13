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
from django.utils.dateformat import format as date_format

from apps.academics.models import Batch, Subject
from apps.core import menus as menu_keys
from apps.core.query import id_param, search_param
from apps.core.responses import forbidden_response
from apps.core.roles import Role
from apps.lectures.forms import ExtendScheduleForm, LectureForm, ScheduleForm
from apps.lectures.models import (
    Lecture,
    LectureStatus,
    RecurringSchedule,
    ScheduleStatus,
)
from apps.lectures.services import (
    SHOW_CHOICES,
    SHOW_UPCOMING,
    LectureDetails,
    SavedLecture,
    ScheduleDetails,
    SchedulePreview,
    create_lecture,
    create_schedule,
    extend_schedule,
    list_lectures,
    list_schedules,
    preview_schedule,
    stop_schedule,
    update_lecture,
    update_schedule,
)
from apps.lectures.times import combine_local, local_date, time_range
from apps.lectures.ui import (
    LectureTable,
    SchedulePreviewList,
    ScheduleTable,
    TeacherLectureTable,
    TeacherScheduleTable,
    stop_dialog,
)
from apps.people.models import TeacherProfile
from apps.ui.components.actions import Button
from apps.ui.components.block_stack import BlockStack
from apps.ui.components.data import EmptyState
from apps.ui.components.forms import CrispyForm, PortalPostForm
from apps.ui.components.layout import LinkTabs, SectionCard
from apps.ui.components.nav import FilterBar, Pagination
from apps.ui.views.pages import FormPage, ListPage, PortalPageView

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

    def teacher_filter(self, value: str) -> dict[str, Any]:
        teachers = (
            TeacherProfile.objects.for_user(self.request.user)
            .select_related("user")
            .order_by("user__first_name", "user__last_name", "pk")
        )
        return {
            "name": "teacher",
            "label": "Teacher",
            "value": value,
            "options": self.options(teachers, "Any teacher"),
        }

    def batch_filter(self, value: str) -> dict[str, Any]:
        batches = Batch.objects.for_user(self.request.user).order_by("name")
        return {
            "name": "batch",
            "label": "Batch",
            "value": value,
            "options": self.options(batches, "Any batch"),
        }

    def filter_fields(self, filters: dict[str, str]) -> list[dict[str, Any]]:
        subjects = Subject.objects.for_user(self.request.user).order_by("name")
        fields = [{"name": "show", "value": filters["show"], "hidden": True}]
        if "teacher" in self.filter_keys:
            fields.append(self.teacher_filter(filters["teacher"]))
        return [
            *fields,
            self.batch_filter(filters["batch"]),
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
            # No title: on the teacher portal it may be another teacher's.
            messages.warning(
                self.request,
                f"{clash.batch.name} also has a lecture on "
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
        lectures = (
            Lecture.objects.for_user(self.request.user)
            .select_related("schedule")
            .prefetch_related("subjects")
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

    def get_subtitle(self) -> str:
        schedule = self.lecture.schedule if self.lecture else None
        if schedule is None:
            return ""
        return (
            f"Part of the schedule {schedule.title}. Changes here apply to this "
            "lecture only; edit the schedule to change all its future lectures."
        )

    def save(self, details: LectureDetails) -> SavedLecture:
        return update_lecture(self.lecture, details)


class TeacherLectureCreatePage(TeacherLectureMixin, LectureCreatePage):
    title = "Create lecture"
    save_label = "Create lecture"
    active_item = "lecture_create"


class TeacherLectureEditPage(TeacherLectureMixin, LectureEditPage):
    pass


# Recurring schedules (roadmap 3.2, SPEC 3 and 4.6)


class ScheduleMixin:
    table_class: type[ScheduleTable] = ScheduleTable

    def schedule_url(self, action: str, **kwargs: Any) -> str:
        return self.url(f"schedule_{action}", **kwargs)


class TeacherScheduleMixin(ScheduleMixin, TeacherLectureMixin):
    active_item = "lecture_schedule"
    table_class = TeacherScheduleTable


class AdminScheduleMixin(ScheduleMixin, AdminLectureMixin):
    pass


class ScheduleListPage(AdminScheduleMixin, LectureListPage):
    title = "Recurring schedules"
    filter_keys = ("teacher", "batch")

    def get_actions(self) -> list[Any]:
        return [Button("Add schedule", url=self.schedule_url("create"), icon="plus")]

    def get_filters(self) -> dict[str, str]:
        return {
            key: search_param(self.request.GET.get(key)) for key in self.filter_keys
        }

    def get_components(self) -> dict[str, Any]:
        filters = self.get_filters()
        rows = list_schedules(
            self.request.user,
            teacher_id=id_param(filters.get("teacher")),
            batch_id=id_param(filters["batch"]),
        )
        page = Paginator(rows, PAGE_SIZE).get_page(self.request.GET.get("page"))
        query = urlencode({key: value for key, value in filters.items() if value})
        return {
            "filters": FilterBar(self.filter_fields(filters)),
            "table": self.schedule_table(list(page.object_list)),
            "pagination": Pagination(page, query=query),
        }

    def filter_fields(self, filters: dict[str, str]) -> list[dict[str, Any]]:
        fields = []
        if "teacher" in self.filter_keys:
            fields.append(self.teacher_filter(filters["teacher"]))
        return [*fields, self.batch_filter(filters["batch"])]

    def schedule_table(self, rows: list[RecurringSchedule]) -> Any:
        mine = RecurringSchedule.objects.for_user(self.request.user)
        if not rows and not mine.exists():
            return EmptyState(
                "No recurring schedules yet.",
                text="A schedule makes a lecture on the same days every week.",
                icon="calendar-days",
                action=Button(
                    "Add your first schedule", url=self.schedule_url("create")
                ),
            )
        return self.table_class(rows)


class TeacherScheduleListPage(TeacherScheduleMixin, ScheduleListPage):
    title = "My schedules"
    filter_keys = ("batch",)


SCHEDULE_FORM_FIELDS = {**FORM_FIELDS, "starts_at": "start_date"}


class ScheduleFormPage(AdminScheduleMixin, LectureFormPage):
    """Two steps: a valid submit shows the preview; the same values sent
    again save (SPEC 4.6: preview the lectures before saving)."""

    form_class = ScheduleForm
    preview_label = "Preview lectures"
    save_label = "Create schedule"
    success_message = "Schedule saved. Its lectures are being added."
    schedule: RecurringSchedule | None = None
    preview: SchedulePreview | None = None

    def zone_name(self) -> str:
        if self.schedule is not None:
            return self.schedule.time_zone
        return timezone.get_current_timezone_name()

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["lecture"] = self.schedule
        kwargs["cancel_url"] = self.schedule_url("list")
        kwargs["zone_label"] = self.zone_name()
        if self.preview is None:
            kwargs["save_label"] = self.preview_label
        return kwargs

    def schedule_details(self, form: ScheduleForm) -> ScheduleDetails:
        data = form.cleaned_data
        batch, subjects = form.selection()
        return ScheduleDetails(
            title=data["title"],
            teacher=form.teacher(),
            batch=batch,
            subjects=subjects,
            weekdays=data["weekdays"],
            start_time=data["start_time"],
            duration_minutes=data["duration_minutes"],
            start_date=data["start_date"],
            end_date=data["end_date"],
            time_zone=self.zone_name(),
            delivery_mode=data["delivery_mode"],
            meeting_url=data["meeting_url"] or "",
            description=data["description"],
        )

    def add_errors(self, form: ScheduleForm, error: ValidationError) -> HttpResponse:
        for name, field_errors in error.message_dict.items():
            name = SCHEDULE_FORM_FIELDS.get(name, name)
            form.add_error(name if name in form.fields else None, field_errors)
        return self.form_invalid(form)

    def form_valid(self, form: ScheduleForm) -> HttpResponse:
        details = self.schedule_details(form)
        if not form.is_confirmed():
            return self.show_preview(form, details)
        try:
            message = self.save_schedule(details)
        except ValidationError as error:
            return self.add_errors(form, error)
        messages.success(self.request, message)
        return HttpResponseRedirect(self.schedule_url("list"))

    def show_preview(self, form: ScheduleForm, details: ScheduleDetails) -> Any:
        try:
            self.preview = preview_schedule(
                self.get_institute(), details, self.schedule
            )
        except ValidationError as error:
            return self.add_errors(form, error)
        data = self.request.POST.copy()
        data["confirm"] = form.fingerprint()
        confirmed = self.form_class(data, **self.get_form_kwargs())
        confirmed.is_valid()
        confirmed.helper.disable_csrf = True
        return self.form_invalid(confirmed)

    def get_form_wrapper(self, form: Any) -> PortalPostForm:
        body = CrispyForm(form=form)
        if self.preview is None:
            return PortalPostForm(action=self.request.path, body=body)
        return PortalPostForm(
            action=self.request.path,
            body=BlockStack(blocks=[self.preview_card(), body]),
        )

    def preview_card(self) -> SectionCard:
        preview = self.preview
        later = (
            f" {preview.later_count} more are added each night as their dates "
            f"come within {preview.horizon_weeks} weeks."
            if preview.later_count
            else ""
        )
        text = (
            "Check the dates, then save below. If you change a value, the "
            "preview is made again." + later
        )
        return SectionCard(
            title=f"{preview.created_count} lectures will be added now",
            icon="calendar-days",
            body=BlockStack(blocks=[text, SchedulePreviewList(preview.planned)]),
        )

    def save_schedule(self, details: ScheduleDetails) -> str:
        create_schedule(self.get_institute(), details)
        return self.success_message


class ScheduleCreatePage(ScheduleFormPage):
    title = "Add recurring schedule"


class ScheduleObjectMixin:
    """Load the schedule only after the access mixins have passed."""

    def get_schedule(self) -> RecurringSchedule:
        schedules = RecurringSchedule.objects.for_user(self.request.user)
        schedules = schedules.select_related("teacher__user", "batch")
        return get_object_or_404(
            schedules.prefetch_related("subjects"), pk=self.kwargs["pk"]
        )


class ScheduleEditPage(ScheduleObjectMixin, ScheduleFormPage):
    title = "Edit recurring schedule"
    save_label = "Save and update lectures"

    def load(self) -> HttpResponse | None:
        denied = super().load()
        if denied is not None:
            return denied
        self.schedule = self.get_schedule()
        return None

    def get_subtitle(self) -> str:
        return (
            "Saving changes this schedule and its lectures that have not "
            "started. Lectures edited one by one stay as they are."
        )

    def get_actions(self) -> list[Any]:
        if self.schedule.status != ScheduleStatus.ACTIVE:
            return []
        return [stop_dialog(self.schedule, self.portal)]

    def get_initial(self) -> dict[str, Any]:
        schedule = self.schedule
        return {
            "title": schedule.title,
            "description": schedule.description,
            "teacher": schedule.teacher_id,
            "batch_subjects": [
                f"{schedule.batch_id}:{subject.pk}"
                for subject in schedule.subjects.all()
            ],
            "weekdays": schedule.weekdays,
            "start_time": schedule.start_time,
            "duration_minutes": schedule.duration_minutes,
            "start_date": schedule.start_date,
            "end_date": schedule.end_date,
            "delivery_mode": schedule.delivery_mode,
            "meeting_url": schedule.meeting_url,
        }

    def save_schedule(self, details: ScheduleDetails) -> str:
        removed = update_schedule(self.schedule, details)
        if removed:
            return f"Schedule saved. {removed} upcoming lectures are being remade."
        return "Schedule saved."


class ScheduleExtendPage(ScheduleObjectMixin, AdminScheduleMixin, FormPage):
    title = "Extend schedule"
    form_class = ExtendScheduleForm

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.schedule = self.get_schedule()
        return super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.schedule = self.get_schedule()
        return super().post(request, *args, **kwargs)

    def get_subtitle(self) -> str:
        end = date_format(self.schedule.end_date, "j M Y")
        return f"{self.schedule.title} ends on {end}. Choose a later date."

    def get_form_kwargs(self) -> dict[str, Any]:
        return {"cancel_url": self.schedule_url("list")}

    def form_valid(self, form: ExtendScheduleForm) -> HttpResponse:
        try:
            extend_schedule(self.schedule, form.cleaned_data["end_date"])
        except ValidationError as error:
            for name, field_errors in error.message_dict.items():
                form.add_error(name if name in form.fields else None, field_errors)
            return self.form_invalid(form)
        messages.success(self.request, "Schedule extended.")
        return HttpResponseRedirect(self.schedule_url("list"))


class ScheduleStopView(ScheduleObjectMixin, AdminScheduleMixin, PortalPageView):
    """POST only, from the confirm dialog."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        schedule = self.get_schedule()
        cancelled = stop_schedule(schedule)
        messages.success(
            request, f"{schedule.title} stopped. {cancelled} lectures cancelled."
        )
        return HttpResponseRedirect(self.schedule_url("list"))


class TeacherScheduleCreatePage(TeacherScheduleMixin, ScheduleCreatePage):
    pass


class TeacherScheduleEditPage(TeacherScheduleMixin, ScheduleEditPage):
    pass


class TeacherScheduleExtendPage(TeacherScheduleMixin, ScheduleExtendPage):
    pass


class TeacherScheduleStopView(TeacherScheduleMixin, ScheduleStopView):
    pass
