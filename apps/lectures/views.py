"""Lecture pages: admin All lectures / Add / Edit, teacher My lectures /
Create / Edit (roadmap 3.1, SPEC 3 and 4.5)."""

from __future__ import annotations

from datetime import MAXYEAR, MINYEAR, date
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
    CALENDAR_MONTH,
    CALENDAR_WEEK,
    JOIN_ENDED,
    JOIN_NONE,
    JOIN_OPEN,
    JOIN_SOON,
    JOIN_WAITING,
    SHOW_CHOICES,
    SHOW_UPCOMING,
    CalendarRange,
    LectureDetails,
    LectureMonitor,
    SavedLecture,
    ScheduleDetails,
    SchedulePreview,
    calendar_lectures,
    calendar_range,
    can_start,
    cancel_lecture,
    create_lecture,
    create_schedule,
    end_lecture,
    extend_schedule,
    join_opens_at,
    join_state,
    join_window_minutes,
    lecture_monitor,
    list_history,
    list_lectures,
    list_schedules,
    next_lecture,
    preview_schedule,
    schedule_problems,
    start_lecture,
    stop_schedule,
    update_lecture,
    update_schedule,
)
from apps.lectures.times import combine_local, local_date, local_time, time_range
from apps.lectures.ui import (
    AdminHistoryTable,
    HistoryTable,
    LectureTable,
    MonitorTable,
    ScheduleTable,
    StudentLectureTable,
    TeacherLectureTable,
    TeacherScheduleTable,
    calendar_days,
    can_cancel,
    cancel_dialog,
    end_dialog,
    join_action,
    lecture_detail_rows,
    lecture_summary,
    meeting_link_button,
    schedule_preview_list,
    start_button,
    stop_dialog,
    up_next_card,
)
from apps.people.models import StudentProfile, TeacherProfile
from apps.ui.components.actions import Button
from apps.ui.components.block_stack import BlockStack
from apps.ui.components.data import DetailList, EmptyState, StatCard
from apps.ui.components.forms import CrispyForm, PortalPostForm
from apps.ui.components.layout import Grid, LinkTabs, LiveRegion, SectionCard
from apps.ui.components.lectures import Calendar
from apps.ui.components.nav import FilterBar, Pagination
from apps.ui.views.pages import (
    DashboardPage,
    DetailPage,
    FormPage,
    ListPage,
    PortalPageView,
)

PAGE_SIZE = 25
SHOW_KEYS = {key for key, _ in SHOW_CHOICES}
STATUS_OPTIONS = [("", "Any status"), *LectureStatus.choices]
DATE_FIELD = {"input_type": "date"}
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
    filter_keys = ("teacher", "batch", "subject", "status", "date_from", "date_to")

    def get_actions(self) -> list[Any]:
        return [Button(self.create_label, url=self.url("create"), icon="plus")]

    def get_filters(self) -> dict[str, str]:
        filters = {
            key: search_param(self.request.GET.get(key)) for key in self.filter_keys
        }
        show = search_param(self.request.GET.get("show"))
        filters["show"] = show if show in SHOW_KEYS else SHOW_UPCOMING
        for key in ("date_from", "date_to"):
            if key in filters and calendar_day(filters[key]) is None:
                filters[key] = ""
        return filters

    def get_rows(self, filters: dict[str, str]) -> Any:
        return list_lectures(
            self.request.user,
            show=filters["show"],
            teacher_id=id_param(filters.get("teacher")),
            batch_id=id_param(filters.get("batch")),
            subject_id=id_param(filters.get("subject")),
            status=filters.get("status", ""),
            date_from=calendar_day(filters.get("date_from")),
            date_to=calendar_day(filters.get("date_to")),
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

    def subject_filter(self, value: str) -> dict[str, Any]:
        subjects = self.subject_rows().order_by("name")
        return {
            "name": "subject",
            "label": "Subject",
            "value": value,
            "options": self.options(subjects, "Any subject"),
        }

    def subject_rows(self) -> Any:
        return Subject.objects.for_user(self.request.user)

    def status_filter(self, value: str) -> dict[str, Any]:
        return {
            "name": "status",
            "label": "Status",
            "value": value,
            "options": STATUS_OPTIONS,
        }

    def date_from_filter(self, value: str) -> dict[str, Any]:
        return {"name": "date_from", "label": "From", "value": value, **DATE_FIELD}

    def date_to_filter(self, value: str) -> dict[str, Any]:
        return {"name": "date_to", "label": "To", "value": value, **DATE_FIELD}

    def filter_fields(self, filters: dict[str, str]) -> list[dict[str, Any]]:
        """One field per ``filter_keys`` entry, built by ``<key>_filter``."""
        return [
            {"name": "show", "value": filters["show"], "hidden": True},
            *(getattr(self, f"{key}_filter")(filters[key]) for key in self.filter_keys),
        ]

    def get_table(self, rows: list[Lecture], filters: dict[str, str]) -> Any:
        if not rows and not self.visible_lectures().exists():
            return self.first_lecture_state()
        return self.table_class(
            rows, empty_title=EMPTY_TITLES[filters["show"]], **self.table_kwargs()
        )

    def table_kwargs(self) -> dict[str, Any]:
        return {"window": join_window_minutes(self.get_institute())}

    def visible_lectures(self) -> Any:
        return Lecture.objects.for_user(self.request.user)

    def first_lecture_state(self) -> EmptyState:
        return EmptyState(
            "No lectures yet.",
            icon="video",
            action=Button(self.first_label, url=self.url("create")),
        )


class TeacherLectureListPage(TeacherLectureMixin, LectureListPage):
    title = "My lectures"
    filter_keys = ("batch", "subject", "status")


class StudentLectureListPage(LectureListPage):
    """Student "My lectures" (SPEC 3): the lectures of the student's batches
    and subjects, read only."""

    portal = "student"
    menu_key = None
    active_item = "lectures"
    allowed_roles = [Role.STUDENT]
    title = "My lectures"
    filter_keys = ("subject",)
    table_class = StudentLectureTable
    empty_text = "Lectures for your batches and subjects show here."

    def get_actions(self) -> list[Any]:
        return []

    def first_lecture_state(self) -> EmptyState:
        return EmptyState("No lectures yet.", text=self.empty_text, icon="video")

    def table_kwargs(self) -> dict[str, Any]:
        return {"join_window": join_window_minutes(self.get_institute())}


class GuardianLectureListPage(StudentLectureListPage):
    """Guardian "Lectures schedule": the student list for one child. With
    more than one child, a filter chooses the child (the first by default)."""

    portal = "guardian"
    active_item = "lecture_schedule"
    allowed_roles = [Role.GUARDIAN]
    title = "Lectures schedule"
    filter_keys = ("child", "subject")
    empty_text = "Your child's lectures show here once they are scheduled."

    @cached_property
    def children(self) -> list[StudentProfile]:
        return list(
            StudentProfile.objects.for_user(self.request.user)
            .select_related("user")
            .order_by("user__first_name", "user__last_name", "pk")
        )

    @cached_property
    def child(self) -> StudentProfile | None:
        wanted = id_param(search_param(self.request.GET.get("child")))
        chosen = [child for child in self.children if child.pk == wanted]
        return (chosen or self.children or [None])[0]

    def get_subtitle(self) -> str:
        return f"Lectures for {self.child}." if self.child else ""

    def get_filters(self) -> dict[str, str]:
        filters = super().get_filters()
        filters["child"] = str(self.child.pk) if self.child else ""
        return filters

    def date_from_filter(self, value: str) -> dict[str, Any]:
        return {"name": "date_from", "label": "From", "value": value, **DATE_FIELD}

    def date_to_filter(self, value: str) -> dict[str, Any]:
        return {"name": "date_to", "label": "To", "value": value, **DATE_FIELD}

    def filter_fields(self, filters: dict[str, str]) -> list[dict[str, Any]]:
        fields = super().filter_fields(filters)
        if len(self.children) < 2:
            return [field for field in fields if field["name"] != "child"]
        return fields

    def child_filter(self, value: str) -> dict[str, Any]:
        return {
            "name": "child",
            "label": "Child",
            "value": value,
            "kept": True,
            "options": [(str(child.pk), str(child)) for child in self.children],
        }

    def subject_rows(self) -> Any:
        if self.child is None:
            return Subject.objects.none()
        return super().subject_rows().filter(student_links__student=self.child)

    def get_rows(self, filters: dict[str, str]) -> Any:
        if self.child is None:
            return Lecture.objects.none()
        return list_lectures(
            self.request.user,
            show=filters["show"],
            subject_id=id_param(filters.get("subject")),
            student_id=self.child.pk,
        )

    def visible_lectures(self) -> Any:
        if self.child is None:
            return Lecture.objects.none()
        return list_lectures(self.request.user, show="all", student_id=self.child.pk)

    def table_kwargs(self) -> dict[str, Any]:
        return {}  # guardians see the lectures; the student joins

    def first_lecture_state(self) -> EmptyState:
        if self.child is None:
            return EmptyState(
                "No children are linked to this account yet.",
                text="Contact the institute office.",
                icon="graduation-cap",
            )
        return super().first_lecture_state()


# Lecture page and states (roadmap 3.5, SPEC 6.4)


class LectureObjectMixin:
    """The lecture from the URL, through ``for_user`` (404 when not visible)."""

    def get_lecture(self) -> Lecture:
        lectures = (
            Lecture.objects.for_user(self.request.user)
            .select_related("teacher__user", "batch", "schedule")
            .prefetch_related("subjects")
        )
        return get_object_or_404(lectures, pk=self.kwargs["pk"])


class LectureDetailPage(LectureObjectMixin, AdminLectureMixin, DetailPage):
    title = "Lecture"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.lecture = self.get_lecture()
        self.title = self.lecture.title
        self.now = timezone.now()
        self.window = join_window_minutes(self.get_institute())
        return super().get(request, *args, **kwargs)

    def get_subtitle(self) -> str:
        return lecture_summary(self.lecture)

    def get_actions(self) -> list[Any]:
        lecture = self.lecture
        actions = self.state_actions()
        link = meeting_link_button(lecture)
        if link is not None:
            actions.append(link)
        if lecture.status == LectureStatus.SCHEDULED:
            url = self.url("edit", pk=lecture.pk)
            actions.append(
                Button("Edit", variant="secondary", url=url, icon="square-pen")
            )
        return actions

    def state_actions(self) -> list[Any]:
        if can_cancel(self.lecture, self.now):
            return [cancel_dialog(self.lecture)]
        return []

    def get_primary_cards(self) -> list[Any]:
        rows = lecture_detail_rows(self.lecture, show_teacher=self.portal == "admin")
        return [SectionCard(title="Details", icon="video", body=DetailList(rows))]


class TeacherLectureDetailPage(TeacherLectureMixin, LectureDetailPage):
    def state_actions(self) -> list[Any]:
        lecture = self.lecture
        if can_start(lecture, now=self.now, window=self.window):
            return [start_button(lecture)]
        if lecture.status == LectureStatus.LIVE:
            return [end_dialog(lecture)]
        return []


class LectureStateView(LectureObjectMixin, PortalPageView):
    """POST only: change a lecture's state, then go back to its page."""

    http_method_names = ["post"]
    success_message = ""

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        lecture = self.get_lecture()
        try:
            self.change(lecture)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, self.success_message.format(title=lecture))
        url = reverse(f"{self.portal}:lecture_detail", kwargs={"pk": lecture.pk})
        return HttpResponseRedirect(url)

    def change(self, lecture: Lecture) -> None:
        raise NotImplementedError


class LectureCancelView(AdminLectureMixin, LectureStateView):
    success_message = "{title} cancelled."

    def change(self, lecture: Lecture) -> None:
        cancel_lecture(lecture)


class TeacherLectureStartView(TeacherLectureMixin, LectureStateView):
    success_message = "{title} started. Students can join now."

    def change(self, lecture: Lecture) -> None:
        start_lecture(lecture, window=join_window_minutes(self.get_institute()))


class TeacherLectureEndView(TeacherLectureMixin, LectureStateView):
    success_message = "{title} ended."

    def change(self, lecture: Lecture) -> None:
        end_lecture(lecture)


class TeacherLectureHistoryPage(LectureListPage):
    """Teacher "Lecture history" (SPEC 3): own finished lectures."""

    portal = "teacher"
    menu_key = None
    active_item = "lecture_history"
    allowed_roles = [Role.TEACHER]
    title = "Lecture history"
    filter_keys = ("batch",)
    history_table = HistoryTable

    def get_actions(self) -> list[Any]:
        return []

    def get_filters(self) -> dict[str, str]:
        return {
            key: search_param(self.request.GET.get(key)) for key in self.filter_keys
        }

    def get_rows(self, filters: dict[str, str]) -> Any:
        return list_history(
            self.request.user,
            teacher_id=id_param(filters.get("teacher")),
            batch_id=id_param(filters.get("batch")),
        )

    def get_components(self) -> dict[str, Any]:
        filters = self.get_filters()
        page = Paginator(self.get_rows(filters), PAGE_SIZE).get_page(
            self.request.GET.get("page")
        )
        query = urlencode({key: value for key, value in filters.items() if value})
        fields = [
            getattr(self, f"{key}_filter")(filters[key]) for key in self.filter_keys
        ]
        return {
            "filters": FilterBar(fields),
            "table": self.history_table(list(page.object_list)),
            "pagination": Pagination(page, query=query),
        }


class AdminLectureHistoryPage(TeacherLectureHistoryPage):
    """Admin "Teacher lecture history" (People menu): every teacher's
    finished lectures, filtered by teacher and batch."""

    portal = "admin"
    menu_key = menu_keys.PEOPLE
    active_item = None
    allowed_roles = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]
    title = "Teacher lecture history"
    filter_keys = ("teacher", "batch")
    history_table = AdminHistoryTable


JOIN_REFUSED = {
    JOIN_SOON: "Join opens {opens}.",
    JOIN_WAITING: "The teacher has not started this lecture yet. Try again soon.",
    JOIN_ENDED: "This lecture has ended.",
    JOIN_NONE: "This lecture has no meeting link to join.",
}


class StudentLectureJoinView(PortalPageView):
    """POST from the Join button. The state is checked again here, so a
    student cannot join early by sending the form by hand (SPEC 6.4)."""

    portal = "student"
    active_item = "lectures"
    allowed_roles = [Role.STUDENT]
    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        lecture = get_object_or_404(
            Lecture.objects.for_user(request.user), pk=kwargs["pk"]
        )
        window = join_window_minutes(self.get_institute())
        state = join_state(lecture, now=timezone.now(), window=window)
        if state == JOIN_OPEN and lecture.meeting_url:
            return HttpResponseRedirect(lecture.meeting_url)
        opens = f"at {local_time(join_opens_at(lecture, window))}"
        messages.warning(request, JOIN_REFUSED[state].format(opens=opens))
        return HttpResponseRedirect(reverse("student:lecture_list"))


def up_next_body(request: HttpRequest, portal: str, institute: Any) -> Any:
    """The "Up next" card for a teacher or student, or an empty state."""
    lecture = next_lecture(request.user)
    if lecture is None:
        return EmptyState(
            "No upcoming lectures",
            text="Your next lecture shows here with a countdown.",
            icon="calendar",
            framed=False,
        )
    refresh_url = reverse(f"{portal}:up_next")
    window = join_window_minutes(institute)
    if portal == "teacher":
        if can_start(lecture, now=timezone.now(), window=window):
            action = start_button(lecture)
        else:
            action = meeting_link_button(lecture)
        return up_next_card(lecture, action=action, refresh_url=refresh_url)
    state = join_state(lecture, now=timezone.now(), window=window)
    return up_next_card(
        lecture,
        action=join_action(lecture, state, window),
        refresh_url=refresh_url,
        teacher=True,
    )


class UpNextCardView(PortalPageView):
    """The card alone, for its HTMX refresh every 30 seconds."""

    portal = "teacher"
    allowed_roles = [Role.TEACHER]

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        body = up_next_body(request, self.portal, self.get_institute())
        return HttpResponse(body.render(request=request))


class StudentUpNextCardView(UpNextCardView):
    portal = "student"
    allowed_roles = [Role.STUDENT]


class TeacherCalendarPage(ListPage):
    """Teacher "Schedule" (SPEC 3): own lectures in a week or month view, in
    the teacher's time zone. Each lecture links to its page."""

    portal = "teacher"
    active_item = "schedule"
    allowed_roles = [Role.TEACHER]
    title = "Schedule"

    def get_actions(self) -> list[Any]:
        url = reverse("teacher:lecture_create")
        return [Button("Create lecture", url=url, icon="plus")]

    def get_components(self) -> dict[str, Any]:
        view = search_param(self.request.GET.get("view"))
        view = view if view == CALENDAR_MONTH else CALENDAR_WEEK
        today = timezone.localdate()
        anchor = calendar_day(self.request.GET.get("date")) or today
        span = calendar_range(view, anchor)
        lectures = calendar_lectures(self.request.user, span.first, span.last)
        days = calendar_days(
            lectures,
            span.days,
            today=today,
            month=span.month,
            url_for=self.lecture_url,
        )
        return {
            "filters": self.view_tabs(view, anchor),
            "table": Calendar(
                days,
                view=view,
                label=calendar_label(span),
                previous_url=self.page_url(view, span.previous),
                today_url=self.page_url(view, today),
                next_url=self.page_url(view, span.next),
                empty_text="No lectures this month.",
            ),
        }

    def page_url(self, view: str, day: date) -> str:
        return "?" + urlencode({"view": view, "date": day.isoformat()})

    def view_tabs(self, view: str, anchor: date) -> LinkTabs:
        return LinkTabs(
            [
                {"id": key, "label": label, "url": self.page_url(key, anchor)}
                for key, label in ((CALENDAR_WEEK, "Week"), (CALENDAR_MONTH, "Month"))
            ],
            active=view,
            label="Calendar views",
        )

    def lecture_url(self, lecture: Lecture) -> str | None:
        return reverse("teacher:lecture_detail", kwargs={"pk": lecture.pk})


def calendar_day(value: str | None) -> date | None:
    """A ``YYYY-MM-DD`` query value, or None. Years at the ends of the range
    are refused, so the previous and next pages cannot overflow."""
    try:
        day = date.fromisoformat(search_param(value))
    except ValueError:
        return None
    return day if MINYEAR < day.year < MAXYEAR else None


def calendar_label(span: CalendarRange) -> str:
    """Example: October 2026, or 12 to 18 Oct 2026."""
    if span.month is not None:
        return date_format(span.month, "F Y")
    first = "j M" if span.first.year == span.last.year else "j M Y"
    return f"{date_format(span.first, first)} to {date_format(span.last, 'j M Y')}"


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
        if self.lecture.status != LectureStatus.SCHEDULED:
            # Audit P3-4: no form that can never be saved.
            messages.error(self.request, "Only a scheduled lecture can be edited.")
            return HttpResponseRedirect(self.url("detail", pk=self.lecture.pk))
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
        return self.table_class(rows, problems=schedule_problems(rows))


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
        self.preview_minutes = details.duration_minutes
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
        minutes = self.preview_minutes
        text = (
            f"Each lecture is {minutes} minutes. New: the lecture is made. "
            "Skipped: the teacher already has a lecture then. Check the dates, "
            "then save. If you change a value below, the preview is made again." + later
        )
        # Save sits above the dates too, so phones need not scroll the whole
        # list and form to reach it (external audit L3).
        save = Button(self.save_label, icon="check", submit=True)
        return SectionCard(
            title=f"{preview.created_count} lectures will be added now",
            icon="calendar-days",
            body=BlockStack(
                blocks=[text, save, schedule_preview_list(preview.planned)]
            ),
        )

    def save_schedule(self, details: ScheduleDetails) -> str:
        create_schedule(self.get_institute(), details)
        return self.success_message


class ScheduleCreatePage(ScheduleFormPage):
    title = "Add recurring schedule"


class ScheduleObjectMixin:
    """Load the schedule only after the access mixins have passed."""

    def refuse_stopped(self, verb: str) -> HttpResponse | None:
        """Audit P3-4: a stopped schedule opens no form; back to the list."""
        if self.schedule.status == ScheduleStatus.ACTIVE:
            return None
        messages.error(self.request, f"A stopped schedule cannot be {verb}.")
        return HttpResponseRedirect(self.schedule_url("list"))

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
        return self.refuse_stopped("edited")

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
        refused = self.refuse_stopped("extended")
        return refused or super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.schedule = self.get_schedule()
        refused = self.refuse_stopped("extended")
        return refused or super().post(request, *args, **kwargs)

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


# Live lecture monitor (roadmap 3.6, SPEC 8 Lectures dashboard)


class LecturesDashboardPage(DashboardPage):
    """Admin "Lectures" dashboard: what is live, late or starting soon, and
    today's lectures by status. The panel reloads itself every 30 seconds."""

    portal = "admin"
    menu_key = menu_keys.DASHBOARDS
    allowed_roles = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]
    title = "Lectures dashboard"
    region_id = "lecture-monitor"

    def get_subtitle(self) -> str:
        return "Live, late and upcoming lectures. Updates every 30 seconds."

    def get_feature(self) -> LiveRegion:
        now = timezone.now()
        data = lecture_monitor(self.request.user, now=now)
        return LiveRegion(
            self.region_id,
            body=Grid([self.stats(data), self.sections(data, now)], variant="stack"),
            url=self.request.path,
        )

    def stats(self, data: LectureMonitor) -> Grid:
        today = data.today
        finished = today.get(LectureStatus.FINISHED, 0)
        not_held = today.get(LectureStatus.NOT_HELD, 0)
        cancelled = today.get(LectureStatus.CANCELLED, 0)
        return Grid(
            [
                StatCard(len(data.live), "Live now", icon="video", tone="lead"),
                StatCard(
                    len(data.late), "Late start", icon="clock", note="Not started yet"
                ),
                StatCard(len(data.soon), "Next 2 hours", icon="calendar"),
                StatCard(
                    data.today_total,
                    "Lectures today",
                    icon="calendar-days",
                    note=(
                        f"{finished} finished, {not_held} not held, "
                        f"{cancelled} cancelled"
                    ),
                ),
            ],
            variant="stats",
        )

    def sections(self, data: LectureMonitor, now: Any) -> Grid:
        cards = [
            ("Live now", "video", data.live, "live"),
            ("Late start", "clock", data.late, "late"),
            ("Starting in the next 2 hours", "calendar", data.soon, "soon"),
        ]
        return Grid(
            [
                SectionCard(
                    title=title,
                    icon=icon,
                    body=MonitorTable(rows, mode=mode, now=now),
                )
                for title, icon, rows, mode in cards
            ],
            variant="stack",
        )
