"""Super Admin institute management views."""

from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.urls import reverse

from apps.core.roles import Role
from apps.institutes.models import Institute
from apps.superadmin.forms import CreateInstituteForm, EditInstituteForm
from apps.superadmin.services import create_institute, list_institutes, update_institute
from apps.ui.components.actions import Button
from apps.ui.components.data import Column, DataTable
from apps.ui.views.pages import FormPage, ListPage


class InstituteListPage(ListPage):
    portal = "super"
    title = "Institutes"
    allowed_roles = [Role.SUPER_ADMIN]
    active_item = "institutes"

    def get_queryset(self):
        return list_institutes()

    def get_components(self) -> dict[str, Any]:
        rows = list(self.get_queryset())

        def edit_link(institute: Institute) -> Button:
            return Button(
                label="Edit",
                url=reverse("super:institute_edit", kwargs={"pk": institute.pk}),
                variant="secondary",
            )

        columns = [
            Column("name", "Name"),
            Column("plan", "Plan", lambda i: i.plan.name if i.plan_id else ""),
            Column("active", "Active", lambda i: "Yes" if i.is_active else "No"),
            Column("edit", "", edit_link),
        ]
        return {"table": DataTable(rows=rows, columns=columns)}


class CreateInstitutePage(FormPage):
    portal = "super"
    title = "Create institute"
    allowed_roles = [Role.SUPER_ADMIN]
    form_class = CreateInstituteForm
    active_item = "institutes_create"

    def get_form_kwargs(self) -> dict[str, Any]:
        return {"cancel_url": reverse("super:institute_list")}

    def get_success_url(self) -> str:
        return reverse("super:institute_list")

    def on_form_valid(self, form: CreateInstituteForm) -> None:
        result = create_institute(
            name=form.cleaned_data["name"],
            plan=form.cleaned_data["plan"],
            admin_email=form.cleaned_data["admin_email"],
            timezone=form.cleaned_data["timezone"],
        )
        messages.success(
            self.request,
            f"Institute created. Set-password link: {result.set_password_path}",
        )


class EditInstitutePage(FormPage):
    portal = "super"
    title = "Edit institute"
    allowed_roles = [Role.SUPER_ADMIN]
    form_class = EditInstituteForm
    active_item = "institutes"

    def dispatch(self, request, *args, **kwargs):
        self.institute_pk = kwargs.get("pk")
        # unscoped: Super Admin resolves institute by primary key across tenants.
        # Global Institute rows are not tenant-scoped.
        self.institute = Institute.objects.select_related("plan").get(
            pk=self.institute_pk
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self) -> dict[str, Any]:
        return {
            "initial": {
                "name": self.institute.name,
                "plan": self.institute.plan_id,
                "is_active": self.institute.is_active,
            },
            "is_active": self.institute.is_active,
            "cancel_url": reverse("super:institute_list"),
        }

    def get_success_url(self) -> str:
        return reverse("super:institute_edit", kwargs={"pk": self.institute.pk})

    def on_form_valid(self, form: EditInstituteForm) -> None:
        update_institute(
            self.institute,
            name=form.cleaned_data["name"],
            plan=form.cleaned_data["plan"],
            is_active=form.cleaned_data["is_active"],
        )
        action = "activated" if self.institute.is_active else "deactivated"
        messages.success(self.request, f"Institute saved ({action} when toggled).")
