"""Admin pages for teachers (People menu, roadmap 2.5a)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse

from apps.academics.models import Batch
from apps.core import menus as menu_keys
from apps.core.roles import Role
from apps.people.forms import TeacherCreateForm, TeacherForm
from apps.people.models import ProfileStatus, TeacherProfile
from apps.people.services import (
    create_teacher,
    list_teachers,
    set_teacher_active,
    update_teacher,
)
from apps.people.ui import TeacherTable, teacher_status_dialog
from apps.ui.components.actions import Button
from apps.ui.components.data import EmptyState
from apps.ui.components.nav import FilterBar, Pagination
from apps.ui.views.pages import FormPage, ListPage, PortalPageView

PAGE_SIZE = 25
STATUS_OPTIONS = [("", "Any status"), *ProfileStatus.choices]


class PeopleAdminMixin:
    portal = "admin"
    menu_key = menu_keys.PEOPLE
    allowed_roles = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]


class TeacherObjectMixin(PeopleAdminMixin):
    """Load the teacher only after the access mixins have passed."""

    teacher: TeacherProfile

    def get_object(self) -> TeacherProfile:
        teachers = TeacherProfile.objects.for_user(self.request.user)
        return get_object_or_404(teachers.select_related("user"), pk=self.kwargs["pk"])


class TeacherListPage(PeopleAdminMixin, ListPage):
    title = "All teachers"

    def get_actions(self) -> list[Any]:
        return [Button("Add teacher", url=reverse("admin:teacher_create"))]

    def get_filters(self) -> dict[str, str]:
        return {
            key: self.request.GET.get(key, "").strip()
            for key in ("q", "batch", "status")
        }

    def get_components(self) -> dict[str, Any]:
        filters = self.get_filters()
        batch_id = int(filters["batch"]) if filters["batch"].isdigit() else None
        teachers = list_teachers(
            self.request.user,
            search=filters["q"],
            batch_id=batch_id,
            status=filters["status"],
        )
        page = Paginator(teachers, PAGE_SIZE).get_page(self.request.GET.get("page"))
        query = urlencode({key: value for key, value in filters.items() if value})
        return {
            "filters": FilterBar(filters=self.filter_fields(filters)),
            "table": self.get_table(list(page.object_list), any(filters.values())),
            "pagination": Pagination(page, query=query),
        }

    def filter_fields(self, filters: dict[str, str]) -> list[dict[str, Any]]:
        batches = Batch.objects.for_user(self.request.user).order_by("name")
        batch_options = [("", "Any batch")] + [
            (str(batch.pk), batch.name) for batch in batches
        ]
        return [
            {"name": "q", "label": "Search", "value": filters["q"]},
            {
                "name": "batch",
                "label": "Batch",
                "value": filters["batch"],
                "options": batch_options,
            },
            {
                "name": "status",
                "label": "Status",
                "value": filters["status"],
                "options": STATUS_OPTIONS,
            },
        ]

    def get_table(self, teachers: list[TeacherProfile], filtered: bool) -> Any:
        if not teachers and not filtered:
            return EmptyState(
                "No teachers yet.",
                action=Button(
                    "Add your first teacher", url=reverse("admin:teacher_create")
                ),
            )
        return TeacherTable(teachers)


class TeacherFormPage(PeopleAdminMixin, FormPage):
    """Maps service errors back onto the form."""

    def get_form_kwargs(self) -> dict[str, Any]:
        return {"user": self.request.user, "cancel_url": reverse("admin:teacher_list")}

    def form_valid(self, form: TeacherForm) -> HttpResponse:
        try:
            self.save(form)
        except ValidationError as error:
            for field, field_errors in error.message_dict.items():
                form.add_error(field if field in form.fields else None, field_errors)
            return self.form_invalid(form)
        return HttpResponseRedirect(reverse("admin:teacher_list"))


class TeacherCreatePage(TeacherFormPage):
    title = "Add teacher"
    form_class = TeacherCreateForm

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
        messages.success(self.request, "Teacher added.")


class TeacherEditPage(TeacherObjectMixin, TeacherFormPage):
    title = "Edit teacher"
    form_class = TeacherForm

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.teacher = self.get_object()
        return super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.teacher = self.get_object()
        return super().post(request, *args, **kwargs)

    def current_selections(self) -> dict:
        current: dict = {}
        links = self.teacher.batch_subjects.select_related("batch", "subject")
        for link in links:
            current.setdefault(link.batch, []).append(link.subject)
        return current

    def get_form_kwargs(self) -> dict[str, Any]:
        teacher = self.teacher
        user = teacher.user
        return {
            **super().get_form_kwargs(),
            "current": self.current_selections(),
            "initial": {
                "full_name": user.get_full_name(),
                "phone": user.phone,
                "email": user.email,
                "cnic": teacher.cnic,
                "address": teacher.address,
                "joining_date": teacher.joining_date,
            },
        }

    def get_actions(self) -> list[Any]:
        return [teacher_status_dialog(self.teacher)]

    def save(self, form: TeacherForm) -> None:
        data = form.cleaned_data
        update_teacher(
            self.teacher,
            full_name=data["full_name"],
            email=data["email"],
            phone=data["phone"],
            cnic=data["cnic"],
            address=data["address"],
            joining_date=data["joining_date"],
            selections=form.selections(),
        )
        messages.success(self.request, "Teacher saved.")


class TeacherStatusView(TeacherObjectMixin, PortalPageView):
    """POST-only activate or deactivate, reached from the confirm dialog."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        teacher = self.get_object()
        action = request.POST.get("action")
        if action not in {"activate", "deactivate"}:
            messages.error(request, "Unknown action.")
        else:
            set_teacher_active(teacher, is_active=action == "activate")
            messages.success(request, f"{teacher} {action}d.")
        return HttpResponseRedirect(reverse("admin:teacher_list"))
