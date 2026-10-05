from __future__ import annotations

from typing import Any

from django.http import HttpResponse
from django.views.generic import TemplateView

from apps.core.mixins.access import (
    MenuRequiredMixin,
    RoleRequiredMixin,
    TenantRequiredMixin,
)
from apps.ui.components.layout import PageHeader, SidebarShell, TopNavShell
from apps.ui.components.page_layouts import (
    DashboardPageBody,
    DetailPageBody,
    FormPageBody,
    ListPageBody,
)


class PortalPageView(
    MenuRequiredMixin,
    RoleRequiredMixin,
    TenantRequiredMixin,
    TemplateView,
):
    template_name = "ui/layouts/portal_page.html"
    portal: str | None = None
    menu_key: str | None = None
    allowed_roles: list[str] = []
    title = ""
    breadcrumb: list[str] = []
    page_layout = "default"

    def get_shell_class(self):
        if self.portal == "admin":
            return TopNavShell
        return SidebarShell

    def get_header(self) -> PageHeader:
        return PageHeader(
            title=self.title,
            breadcrumb=self.breadcrumb,
            actions=self.get_actions(),
        )

    def get_actions(self) -> list[Any]:
        return []

    def get_components(self) -> dict[str, Any]:
        return {}

    def get_institute(self) -> Any | None:
        return getattr(self.request, "institute", None) or getattr(
            self.request.user, "institute", None
        )

    def build_page_body(self, context: dict[str, Any]):
        header = context["header"]
        layout = self.page_layout
        if layout == "dashboard":
            return DashboardPageBody(
                header=header,
                stat_cards=context.get("stat_cards", []),
                quick_actions=context.get("quick_actions", []),
                sections=context.get("sections", []),
            )
        if layout == "list":
            return ListPageBody(
                header=header,
                filters=context.get("filters"),
                table=context.get("table"),
            )
        if layout == "detail":
            return DetailPageBody(
                header=header,
                primary_cards=context.get("primary_cards", []),
                sidebar_cards=context.get("sidebar_cards", []),
            )
        if layout == "form":
            return FormPageBody(header=header, form=context.get("form"))
        return ListPageBody(header=header)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["portal"] = self.portal
        ctx["page_title"] = self.title
        ctx["header"] = self.get_header()
        ctx.update(self.get_components())
        return ctx

    def render_to_response(
        self, context: dict[str, Any], **response_kwargs: Any
    ) -> HttpResponse:
        body = self.build_page_body(context)
        shell_class = self.get_shell_class()
        shell = shell_class(
            portal=self.portal,
            user=self.request.user,
            active=self.menu_key,
            institute=self.get_institute(),
            page_title=self.title,
            content=body,
        )
        return HttpResponse(shell.render(request=self.request), **response_kwargs)


class DashboardPage(PortalPageView):
    page_layout = "dashboard"

    def get_stat_cards(self) -> list[Any]:
        return []

    def get_quick_actions(self) -> list[Any]:
        return []

    def get_sections(self) -> list[Any]:
        return []

    def get_components(self) -> dict[str, Any]:
        return {
            "stat_cards": self.get_stat_cards(),
            "quick_actions": self.get_quick_actions(),
            "sections": self.get_sections(),
        }


class ListPage(PortalPageView):
    page_layout = "list"
    table_class = None
    filter_class = None

    def get_queryset(self) -> Any:
        return []

    def get_components(self) -> dict[str, Any]:
        components: dict[str, Any] = {}
        if self.filter_class is not None:
            components["filters"] = self.filter_class(self.request)
        if self.table_class is not None:
            components["table"] = self.table_class(self.get_queryset())
        return components


class DetailPage(PortalPageView):
    page_layout = "detail"

    def get_primary_cards(self) -> list[Any]:
        return []

    def get_sidebar_cards(self) -> list[Any]:
        return []

    def get_components(self) -> dict[str, Any]:
        return {
            "primary_cards": self.get_primary_cards(),
            "sidebar_cards": self.get_sidebar_cards(),
        }


class FormPage(PortalPageView):
    page_layout = "form"
    form_class = None

    def get_form(self) -> Any:
        if self.form_class is None:
            raise ValueError("FormPage requires form_class")
        return self.form_class()

    def get_components(self) -> dict[str, Any]:
        return {"form": self.get_form()}
