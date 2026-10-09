"""Super Admin institute management views."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import patch_cache_control
from django.utils.dateformat import format as format_date

from apps.accounts.services import reissue_set_password_token, set_password_path
from apps.core.query import search_param
from apps.core.roles import Role
from apps.institutes.models import Institute
from apps.superadmin.forms import CreateInstituteForm, EditInstituteForm
from apps.superadmin.services import (
    create_institute,
    first_institute_admin,
    list_institutes,
    set_institute_active,
    update_institute,
)
from apps.ui.components.actions import Button, ConfirmDialog, CopyField
from apps.ui.components.block_stack import BlockStack
from apps.ui.components.data import Badge, Column, DataTable
from apps.ui.components.layout import SectionCard
from apps.ui.components.nav import FilterBar, Pagination
from apps.ui.views.pages import DetailPage, FormPage, ListPage, PortalPageView

PAGE_SIZE = 25


def _status_badge(institute: Institute) -> Badge:
    if institute.is_active:
        return Badge("Active", tone="success")
    return Badge("Inactive", tone="neutral")


def _edit_button(institute: Institute) -> Button:
    return Button(
        label="Edit",
        url=reverse("super:institute_edit", kwargs={"pk": institute.pk}),
        variant="secondary",
    )


class SuperAdminPageMixin:
    portal = "super"
    allowed_roles = [Role.SUPER_ADMIN]


class InstituteListPage(SuperAdminPageMixin, ListPage):
    title = "Institutes"
    active_item = "institutes"

    def get_search(self) -> str:
        return search_param(self.request.GET.get("q"))

    def get_actions(self) -> list[Any]:
        return [Button("Create institute", url=reverse("super:institute_create"))]

    def get_components(self) -> dict[str, Any]:
        search = self.get_search()
        page = Paginator(list_institutes(search), PAGE_SIZE).get_page(
            self.request.GET.get("page")
        )
        columns = [
            Column("name", "Name"),
            Column("plan", "Plan", lambda i: i.plan.name),
            Column("status", "Status", _status_badge),
            Column("users", "Users", lambda i: i.user_count),
            Column(
                "created",
                "Created",
                lambda i: format_date(timezone.localtime(i.created_at), "j M Y"),
            ),
            Column("edit", "", _edit_button),
        ]
        filter_field = {"name": "q", "label": "Search by name", "value": search}
        return {
            "filters": FilterBar(filters=[filter_field]),
            "table": DataTable(
                rows=list(page.object_list),
                columns=columns,
                empty_title="No institutes found.",
            ),
            "pagination": Pagination(
                page, query=urlencode({"q": search}) if search else ""
            ),
        }


class CreateInstitutePage(SuperAdminPageMixin, FormPage):
    title = "Create institute"
    form_class = CreateInstituteForm
    active_item = "institutes_create"

    def get_form_kwargs(self) -> dict[str, Any]:
        return {"cancel_url": reverse("super:institute_list")}

    def form_valid(self, form: CreateInstituteForm) -> HttpResponse:
        result = create_institute(
            name=form.cleaned_data["name"],
            plan=form.cleaned_data["plan"],
            admin_email=form.cleaned_data["admin_email"],
            admin_first_name=form.cleaned_data["admin_first_name"],
            admin_last_name=form.cleaned_data["admin_last_name"],
            timezone=form.cleaned_data["timezone"],
            currency_code=form.cleaned_data["currency_code"],
        )
        # The link is shown once in this response only; never in messages or logs.
        link = self.request.build_absolute_uri(result.set_password_path)
        context = self.get_context_data()
        context["form"] = SectionCard(
            title=f"{result.institute.name} created",
            body=BlockStack(
                blocks=[
                    "Send this link to the admin so they can set a password. "
                    "It is shown only once.",
                    CopyField("Set-password link", link),
                    Button(
                        "Back to institutes",
                        url=reverse("super:institute_list"),
                        variant="secondary",
                    ),
                ]
            ),
        )
        response = self.render_to_response(context, status=200)
        # The one-time link must not stay in a browser or proxy cache (M8).
        patch_cache_control(response, no_store=True, private=True)
        return response


class InstituteObjectMixin:
    """Load the institute only after the access mixins have passed."""

    institute: Institute

    def get_object(self) -> Institute:
        return get_object_or_404(
            Institute.objects.select_related("plan"), pk=self.kwargs["pk"]
        )


class EditInstitutePage(SuperAdminPageMixin, InstituteObjectMixin, FormPage):
    title = "Edit institute"
    form_class = EditInstituteForm
    active_item = "institutes"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.institute = self.get_object()
        return super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.institute = self.get_object()
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self) -> dict[str, Any]:
        institute = self.institute
        return {
            "initial": {
                "name": institute.name,
                "plan": institute.plan_id,
                "timezone": institute.timezone,
                "currency_code": institute.currency_code,
            },
            "cancel_url": reverse("super:institute_list"),
        }

    def get_actions(self) -> list[Any]:
        return [self.status_action(), self.link_action()]

    def link_action(self) -> ConfirmDialog:
        return ConfirmDialog(
            "Make a new sign-in link for this institute's admin? Older unused "
            "links stop working.",
            "New sign-in link",
            url=reverse("super:institute_admin_link", kwargs={"pk": self.institute.pk}),
            variant="primary",
        )

    def status_action(self) -> ConfirmDialog:
        institute = self.institute
        url = reverse("super:institute_status", kwargs={"pk": institute.pk})
        if institute.is_active:
            return ConfirmDialog(
                f"Deactivate {institute.name}? Its users will not be able to sign in.",
                "Deactivate",
                url=url,
                fields=[("action", "deactivate")],
            )
        return ConfirmDialog(
            f"Activate {institute.name}? Its users can sign in again.",
            "Activate",
            url=url,
            variant="primary",
            fields=[("action", "activate")],
        )

    def get_success_url(self) -> str:
        return reverse("super:institute_edit", kwargs={"pk": self.institute.pk})

    def on_form_valid(self, form: EditInstituteForm) -> None:
        update_institute(
            self.institute,
            name=form.cleaned_data["name"],
            plan=form.cleaned_data["plan"],
            timezone=form.cleaned_data["timezone"],
            currency_code=form.cleaned_data["currency_code"],
        )
        messages.success(self.request, "Institute saved.")


class InstituteStatusView(SuperAdminPageMixin, InstituteObjectMixin, PortalPageView):
    """POST-only activate/deactivate, reached from the confirm dialog."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        institute = self.get_object()
        action = request.POST.get("action")
        if action not in {"activate", "deactivate"}:
            messages.error(request, "Unknown action.")
        else:
            set_institute_active(institute, is_active=action == "activate")
            messages.success(request, f"{institute.name} {action}d.")
        return HttpResponseRedirect(
            reverse("super:institute_edit", kwargs={"pk": institute.pk})
        )


class InstituteAdminLinkPage(SuperAdminPageMixin, InstituteObjectMixin, DetailPage):
    """POST-only: a new one-time sign-in link for the institute admin (M2)."""

    http_method_names = ["post"]
    title = "New sign-in link"
    active_item = "institutes"

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.institute = self.get_object()
        self.admin = first_institute_admin(self.institute)
        if self.admin is not None:
            self.link = request.build_absolute_uri(
                set_password_path(reissue_set_password_token(self.admin).key)
            )
        response = self.render_to_response(self.get_context_data())
        patch_cache_control(response, no_store=True, private=True)
        return response

    def get_primary_cards(self) -> list[Any]:
        back = Button(
            "Back to institute",
            url=reverse("super:institute_edit", kwargs={"pk": self.institute.pk}),
            variant="secondary",
        )
        if self.admin is None:
            return [
                SectionCard(
                    title=self.institute.name,
                    body=BlockStack(
                        blocks=["This institute has no active admin.", back]
                    ),
                )
            ]
        return [
            SectionCard(
                title=f"Link for {self.admin.email}",
                body=BlockStack(
                    blocks=[
                        "Send this link to the admin. It is shown only once, and "
                        "older unused links no longer work.",
                        CopyField("Set-password link", self.link),
                        back,
                    ]
                ),
            )
        ]
