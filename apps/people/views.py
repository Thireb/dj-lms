"""Admin pages for teachers and students (People menu, roadmap 2.5)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from django.contrib import messages
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import patch_cache_control
from django.utils.dateformat import format as format_date

from apps.academics.models import Batch, ClassLabel
from apps.core import menus as menu_keys
from apps.core.menus import user_has_menu
from apps.core.roles import Role
from apps.people.bulk_upload import (
    RowCheck,
    UploadError,
    build_template,
    check_rows,
    import_rows,
    read_rows,
)
from apps.people.dashboard import admin_dashboard
from apps.people.forms import (
    PersonForm,
    StudentEnrolForm,
    StudentForm,
    StudentUploadForm,
    TeacherCreateForm,
    TeacherForm,
)
from apps.people.models import ProfileStatus, StudentProfile, TeacherProfile
from apps.people.services import (
    StudentDetails,
    create_teacher,
    enrol_student,
    list_portal_access,
    list_students,
    list_teachers,
    set_portal_blocked,
    set_portal_exempt,
    set_student_active,
    set_teacher_active,
    update_student,
    update_teacher,
)
from apps.people.ui import (
    BulkPreviewTable,
    PortalAccessTable,
    RecentStudentTable,
    RecentTeacherTable,
    StudentTable,
    TeacherTable,
    profile_status_dialog,
)
from apps.ui.components.actions import (
    Button,
    ConfirmDialog,
    QuickAction,
    SignOutForm,
)
from apps.ui.components.block_stack import BlockStack
from apps.ui.components.data import EmptyState, ProgressBar, StatCard
from apps.ui.components.forms import CrispyForm, PortalPostForm
from apps.ui.components.layout import HeroBanner, PublicFormShell, SectionCard
from apps.ui.components.nav import FilterBar, Pagination
from apps.ui.views.pages import (
    DashboardPage,
    DetailPage,
    FormPage,
    ListPage,
    PortalPageView,
)

PAGE_SIZE = 25
STATUS_OPTIONS = [("", "Any status"), *ProfileStatus.choices]


class PeopleAdminMixin:
    portal = "admin"
    menu_key = menu_keys.PEOPLE
    allowed_roles = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]
    url_prefix = ""

    def url(self, action: str, **kwargs: Any) -> str:
        return reverse(f"admin:{self.url_prefix}_{action}", kwargs=kwargs or None)


class ProfileObjectMixin(PeopleAdminMixin):
    """Load the profile only after the access mixins have passed."""

    model: type[StudentProfile] | type[TeacherProfile]

    def get_object(self) -> StudentProfile | TeacherProfile:
        profiles = self.model.objects.for_user(self.request.user)
        return get_object_or_404(profiles.select_related("user"), pk=self.kwargs["pk"])


# Lists


class PeopleListPage(PeopleAdminMixin, ListPage):
    filter_keys = ("q", "batch", "status")
    noun = ""
    plural = ""

    def get_actions(self) -> list[Any]:
        return [Button(self.create_label, url=self.url("create"))]

    def get_filters(self) -> dict[str, str]:
        return {key: self.request.GET.get(key, "").strip() for key in self.filter_keys}

    @staticmethod
    def id_filter(value: str) -> int | None:
        return int(value) if value.isdigit() else None

    def get_components(self) -> dict[str, Any]:
        filters = self.get_filters()
        rows = self.get_rows(filters)
        page = Paginator(rows, PAGE_SIZE).get_page(self.request.GET.get("page"))
        query = urlencode({key: value for key, value in filters.items() if value})
        return {
            "filters": FilterBar(filters=self.filter_fields(filters)),
            "table": self.get_table(list(page.object_list), any(filters.values())),
            "pagination": Pagination(page, query=query),
        }

    def options(self, model: type, empty_label: str) -> list[tuple[str, str]]:
        rows = model.objects.for_user(self.request.user).order_by("name")
        return [("", empty_label)] + [(str(row.pk), row.name) for row in rows]

    def filter_fields(self, filters: dict[str, str]) -> list[dict[str, Any]]:
        return [
            {"name": "q", "label": "Search", "value": filters["q"]},
            {
                "name": "batch",
                "label": "Batch",
                "value": filters["batch"],
                "options": self.options(Batch, "Any batch"),
            },
            {
                "name": "status",
                "label": "Status",
                "value": filters["status"],
                "options": STATUS_OPTIONS,
            },
        ]

    def get_table(self, rows: list[Any], filtered: bool) -> Any:
        if not rows and not filtered:
            return EmptyState(
                f"No {self.plural} yet.",
                action=Button(self.first_label, url=self.url("create")),
            )
        return self.table_class(rows)


class TeacherListPage(PeopleListPage):
    title = "All teachers"
    url_prefix = "teacher"
    plural = "teachers"
    create_label = "Add teacher"
    first_label = "Add your first teacher"
    table_class = TeacherTable

    def get_rows(self, filters: dict[str, str]) -> Any:
        return list_teachers(
            self.request.user,
            search=filters["q"],
            batch_id=self.id_filter(filters["batch"]),
            status=filters["status"],
        )


class StudentListPage(PeopleListPage):
    title = "All students"
    url_prefix = "student"
    plural = "students"
    create_label = "Enrol student"
    first_label = "Enrol your first student"
    table_class = StudentTable
    filter_keys = ("q", "batch", "class_label", "status")

    def get_rows(self, filters: dict[str, str]) -> Any:
        return list_students(
            self.request.user,
            search=filters["q"],
            batch_id=self.id_filter(filters["batch"]),
            class_label_id=self.id_filter(filters["class_label"]),
            status=filters["status"],
        )

    def filter_fields(self, filters: dict[str, str]) -> list[dict[str, Any]]:
        fields = super().filter_fields(filters)
        class_filter = {
            "name": "class_label",
            "label": "Class",
            "value": filters["class_label"],
            "options": self.options(ClassLabel, "Any class"),
        }
        return [*fields[:2], class_filter, *fields[2:]]


# Forms


class PeopleFormPage(PeopleAdminMixin, FormPage):
    """Maps service errors back onto the form, then returns to the list."""

    success_message = ""

    def get_form_kwargs(self) -> dict[str, Any]:
        return {"user": self.request.user, "cancel_url": self.url("list")}

    def form_valid(self, form: PersonForm) -> HttpResponse:
        try:
            self.save(form)
        except ValidationError as error:
            for field, field_errors in error.message_dict.items():
                form.add_error(field if field in form.fields else None, field_errors)
            return self.form_invalid(form)
        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.url("list"))


class ProfileEditPage(ProfileObjectMixin, PeopleFormPage):
    success_message = "Changes saved."
    profile: StudentProfile | TeacherProfile

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.profile = self.get_object()
        return super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.profile = self.get_object()
        return super().post(request, *args, **kwargs)

    def current_selections(self) -> dict:
        current: dict = {}
        links = self.profile.batch_subjects.select_related("batch", "subject")
        for link in links:
            current.setdefault(link.batch, []).append(link.subject)
        return current

    def get_form_kwargs(self) -> dict[str, Any]:
        return {
            **super().get_form_kwargs(),
            "current": self.current_selections(),
            "initial": self.get_initial(),
        }

    def get_actions(self) -> list[Any]:
        return [profile_status_dialog(self.profile)]


class TeacherCreatePage(PeopleFormPage):
    title = "Add teacher"
    url_prefix = "teacher"
    form_class = TeacherCreateForm
    success_message = "Teacher added."

    def save(self, form: TeacherCreateForm) -> None:
        data = form.cleaned_data
        create_teacher(
            self.get_institute(),
            full_name=data["full_name"],
            email=data["email"],
            password=data["password"],
            phone=data["phone"],
            cnic=data["cnic"],
            address=data["address"],
            joining_date=data["joining_date"],
            selections=form.selections(),
        )


class TeacherEditPage(ProfileEditPage):
    title = "Edit teacher"
    url_prefix = "teacher"
    model = TeacherProfile
    form_class = TeacherForm
    success_message = "Teacher saved."

    def get_initial(self) -> dict[str, Any]:
        teacher = self.profile
        return {
            "full_name": teacher.user.get_full_name(),
            "phone": teacher.user.phone,
            "email": teacher.user.email,
            "cnic": teacher.cnic,
            "address": teacher.address,
            "joining_date": teacher.joining_date,
        }

    def save(self, form: TeacherForm) -> None:
        data = form.cleaned_data
        update_teacher(
            self.profile,
            full_name=data["full_name"],
            email=data["email"],
            phone=data["phone"],
            cnic=data["cnic"],
            address=data["address"],
            joining_date=data["joining_date"],
            selections=form.selections(),
        )


def _student_details(data: dict[str, Any]) -> StudentDetails:
    return StudentDetails(
        full_name=data["full_name"],
        phone=data["phone"],
        guardian_phone=data["guardian_phone"],
        father_name=data["father_name"],
        cnic=data["cnic"],
        date_of_birth=data["date_of_birth"],
        gender=data["gender"],
        class_label=data["class_label"],
        address=data["address"],
        city=data["city"],
    )


class StudentEnrolPage(PeopleFormPage):
    title = "Enrol student"
    url_prefix = "student"
    form_class = StudentEnrolForm
    success_message = "Student enrolled."

    def save(self, form: StudentEnrolForm) -> None:
        data = form.cleaned_data
        enrol_student(
            self.get_institute(),
            _student_details(data),
            email=data["email"],
            password=data["password"],
            selections=form.selections(),
            guardian_name=data["guardian_name"],
            guardian_email=data["guardian_email"],
            guardian_password=data["guardian_password"],
        )


class StudentEditPage(ProfileEditPage):
    title = "Edit student"
    url_prefix = "student"
    model = StudentProfile
    form_class = StudentForm
    success_message = "Student saved."

    def get_form_kwargs(self) -> dict[str, Any]:
        return {**super().get_form_kwargs(), "current_label": self.profile.class_label}

    def get_initial(self) -> dict[str, Any]:
        student = self.profile
        return {
            "full_name": student.user.get_full_name(),
            "father_name": student.father_name,
            "cnic": student.cnic,
            "date_of_birth": student.date_of_birth,
            "gender": student.gender,
            "class_label": student.class_label_id,
            "phone": student.user.phone,
            "guardian_phone": student.guardian_phone,
            "address": student.address,
            "city": student.city,
            "email": student.user.email,
        }

    def save(self, form: StudentForm) -> None:
        data = form.cleaned_data
        update_student(
            self.profile,
            _student_details(data),
            email=data["email"],
            selections=form.selections(),
        )


# Status


class ProfileStatusView(ProfileObjectMixin, PortalPageView):
    """POST-only activate or deactivate, reached from the confirm dialog."""

    http_method_names = ["post"]
    set_active: Callable[..., Any]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        profile = self.get_object()
        action = request.POST.get("action")
        if action not in {"activate", "deactivate"}:
            messages.error(request, "Unknown action.")
        else:
            self.set_active(profile, is_active=action == "activate")
            messages.success(request, f"{profile} {action}d.")
        return HttpResponseRedirect(self.url("list"))


class TeacherStatusView(ProfileStatusView):
    url_prefix = "teacher"
    model = TeacherProfile
    set_active = staticmethod(set_teacher_active)


class StudentStatusView(ProfileStatusView):
    url_prefix = "student"
    model = StudentProfile
    set_active = staticmethod(set_student_active)


# Bulk upload (roadmap 2.6, SPEC 5)

UPLOAD_MAX_AGE = 30 * 60  # seconds a checked file stays importable


def _students(count: int) -> str:
    return f"{count} student" if count == 1 else f"{count} students"


def _upload_salt(request: HttpRequest) -> str:
    # The signed rows only work for the same admin in the same institute.
    return f"people.bulk-upload:{request.user.pk}:{request.user.institute_id}"


class StudentBulkUploadPage(PeopleAdminMixin, DetailPage):
    """Upload the file, then see every row checked before anything is saved."""

    title = "Bulk upload students"
    url_prefix = "student"
    checks: list[RowCheck] | None = None
    form: StudentUploadForm | None = None

    def get_actions(self) -> list[Any]:
        return [
            Button(
                "Download template",
                url=self.url("bulk_template"),
                variant="secondary",
            )
        ]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.form = StudentUploadForm(
            request.POST, request.FILES, cancel_url=self.url("list")
        )
        if self.form.is_valid():
            try:
                rows = read_rows(self.form.cleaned_data["file"])
            except UploadError as error:
                self.form.add_error("file", str(error))
            else:
                self.checks = check_rows(self.get_institute(), rows)
        response = self.render_to_response(self.get_context_data())
        # The preview carries the checked rows, passwords included.
        patch_cache_control(response, no_store=True, private=True)
        return response

    def get_primary_cards(self) -> list[Any]:
        form = self.form or StudentUploadForm(cancel_url=self.url("list"))
        form.helper.disable_csrf = True
        cards = [
            SectionCard(
                title="Upload a file",
                body=PortalPostForm(
                    action=self.url("bulk_upload"), body=CrispyForm(form=form)
                ),
            )
        ]
        if self.checks is not None:
            cards.append(self.preview_card())
        return cards

    def preview_card(self) -> SectionCard:
        good = [row for row in self.checks if row.ok]
        bad = len(self.checks) - len(good)
        blocks: list[Any] = [
            f"Rows ready: {len(good)}. Rows with errors (skipped): {bad}.",
            BulkPreviewTable(self.checks),
        ]
        if good:
            ready = [{"number": row.number, "values": row.values} for row in good]
            payload = signing.dumps(
                ready, salt=_upload_salt(self.request), compress=True
            )
            blocks.append(
                ConfirmDialog(
                    f"Import {_students(len(good))}? Each one gets a student and a "
                    "guardian sign-in.",
                    f"Import {_students(len(good))}",
                    url=self.url("bulk_import"),
                    variant="primary",
                    fields=[("rows", payload)],
                )
            )
        return SectionCard(title="Check the rows", body=BlockStack(blocks=blocks))


class StudentBulkImportView(PeopleAdminMixin, PortalPageView):
    """POST-only: import the rows checked on the preview page."""

    http_method_names = ["post"]
    url_prefix = "student"

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        try:
            rows = signing.loads(
                request.POST.get("rows", ""),
                salt=_upload_salt(request),
                max_age=UPLOAD_MAX_AGE,
            )
        except signing.BadSignature:
            messages.error(request, "This upload has expired. Upload the file again.")
            return HttpResponseRedirect(self.url("bulk_upload"))
        result = import_rows(self.get_institute(), rows)
        if result.codes:
            messages.success(
                request,
                f"Imported {_students(len(result.codes))}: "
                f"{result.codes[0]} to {result.codes[-1]}.",
            )
        for row in result.failed:
            messages.error(request, f"Row {row.number}: {' '.join(row.errors)}")
        return HttpResponseRedirect(self.url("list"))


class StudentBulkTemplateView(PeopleAdminMixin, PortalPageView):
    """The empty Excel template with a Help sheet."""

    url_prefix = "student"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        response = HttpResponse(
            build_template(),
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = (
            'attachment; filename="student-upload-template.xlsx"'
        )
        return response


# Admin main dashboard (roadmap 2.4, SPEC 8)


class AdminDashboardPage(DashboardPage):
    """Counts and recent people. Later phases add lectures, fees and approvals."""

    portal = "admin"
    menu_key = menu_keys.DASHBOARDS
    allowed_roles = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]
    title = "Main dashboard"

    # (label, icon, url name, menu key the link needs)
    QUICK_ACTIONS = [
        ("Enrol student", "user-plus", "admin:student_create", menu_keys.PEOPLE),
        ("Add teacher", "chalkboard-user", "admin:teacher_create", menu_keys.PEOPLE),
        ("Bulk upload", "upload", "admin:student_bulk_upload", menu_keys.PEOPLE),
        ("Add batch", "users", "admin:batch_create", menu_keys.INSTITUTE),
    ]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        self.data = admin_dashboard(self.request.user)
        return super().get_context_data(**kwargs)

    def can_open(self, key: str) -> bool:
        return user_has_menu(self.request.user, key)

    def get_hero(self) -> HeroBanner:
        today = format_date(timezone.localdate(), "l, j M Y")
        return HeroBanner(title=self.get_institute().name, subtitle=today)

    def get_stat_cards(self) -> list[Any]:
        data = self.data
        students, teachers = data.students, data.teachers
        return [
            StatCard(
                students.total,
                "Students",
                note=f"{students.active} active, {students.inactive} inactive",
                icon="user-graduate",
            ),
            StatCard(
                teachers.total,
                "Teachers",
                note=f"{teachers.active} active, {teachers.inactive} inactive",
                icon="chalkboard-user",
            ),
            StatCard(
                data.batches_running,
                "Running batches",
                note=f"With active students, of {data.batches_total} batches",
                icon="users",
            ),
        ]

    def get_quick_actions(self) -> list[Any]:
        return [
            QuickAction(label, icon, reverse(url_name))
            for label, icon, url_name, key in self.QUICK_ACTIONS
            if self.can_open(key)
        ]

    def get_sections(self) -> list[Any]:
        data = self.data
        people_link = self.can_open(menu_keys.PEOPLE)
        return [
            SectionCard(
                title="Active people",
                body=BlockStack(
                    blocks=[
                        ProgressBar(
                            data.students.active_percent,
                            label=f"Students active: {data.students.active} "
                            f"of {data.students.total}",
                            tone="success",
                        ),
                        ProgressBar(
                            data.teachers.active_percent,
                            label=f"Teachers active: {data.teachers.active} "
                            f"of {data.teachers.total}",
                            tone="success",
                        ),
                    ]
                ),
            ),
            SectionCard(
                title="Recent students",
                body=RecentStudentTable(data.recent_students),
                link_url=reverse("admin:student_list") if people_link else None,
            ),
            SectionCard(
                title="Recent teachers",
                body=RecentTeacherTable(data.recent_teachers),
                link_url=reverse("admin:teacher_list") if people_link else None,
            ),
        ]


# Portal access (roadmap 2.7, SPEC 3 Portal Access and 6.2)

ACCESS_PAUSED = "Access paused. Please contact the institute office"


def access_paused_response(request: HttpRequest) -> HttpResponse:
    """The full page a blocked student sees instead of the student portal."""
    institute = getattr(request, "institute", None)
    phone = getattr(institute, "phone", "")
    message = f"{ACCESS_PAUSED} at {phone}." if phone else f"{ACCESS_PAUSED}."
    card = SectionCard(
        title="Access paused",
        body=BlockStack(
            blocks=[message, SignOutForm(logout_url=reverse("accounts:logout"))]
        ),
    )
    shell = PublicFormShell(page_title="Access paused", content=card)
    return HttpResponse(shell.render(request=request), status=403)


YES_NO_OPTIONS = [("", "Any"), ("yes", "Yes"), ("no", "No")]


class PortalAccessPage(PeopleListPage):
    title = "Portal access"
    url_prefix = "student"
    plural = "students"
    filter_keys = ("q", "blocked", "exempt")
    table_class = PortalAccessTable

    def get_actions(self) -> list[Any]:
        return []

    def get_rows(self, filters: dict[str, str]) -> Any:
        return list_portal_access(
            self.request.user,
            search=filters["q"],
            blocked=filters["blocked"],
            exempt=filters["exempt"],
        )

    def filter_fields(self, filters: dict[str, str]) -> list[dict[str, Any]]:
        return [
            {"name": "q", "label": "Search", "value": filters["q"]},
            {
                "name": "blocked",
                "label": "Blocked",
                "value": filters["blocked"],
                "options": YES_NO_OPTIONS,
            },
            {
                "name": "exempt",
                "label": "Exempt",
                "value": filters["exempt"],
                "options": YES_NO_OPTIONS,
            },
        ]

    def get_table(self, rows: list[Any], filtered: bool) -> Any:
        if not rows and not filtered:
            return EmptyState(
                "No students yet.",
                action=Button("Enrol your first student", url=self.url("create")),
            )
        return self.table_class(rows)


class PortalAccessActionView(ProfileObjectMixin, PortalPageView):
    """POST-only block, unblock, exempt or remove exemption for one student."""

    http_method_names = ["post"]
    url_prefix = "student"
    model = StudentProfile
    ACTIONS = {
        "block": (set_portal_blocked, {"blocked": True}, "{name} blocked."),
        "unblock": (set_portal_blocked, {"blocked": False}, "{name} unblocked."),
        "exempt": (set_portal_exempt, {"exempt": True}, "{name} is exempt."),
        "unexempt": (
            set_portal_exempt,
            {"exempt": False},
            "{name} is no longer exempt.",
        ),
    }

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        student = self.get_object()
        action = self.ACTIONS.get(request.POST.get("action", ""))
        if action is None:
            messages.error(request, "Unknown action.")
        else:
            setter, values, done = action
            setter(student, **values)
            messages.success(request, done.format(name=student))
        return HttpResponseRedirect(reverse("admin:portal_access"))
