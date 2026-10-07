"""Admin pages for the class, batch and subject lists (Institute menu)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse

from apps.academics.forms import NameRowForm
from apps.academics.models import Batch, ClassLabel, NameList, Subject
from apps.academics.services import (
    create_name_row,
    list_name_rows,
    rename_name_row,
    set_name_row_active,
)
from apps.academics.ui import NameListTable, status_dialog
from apps.core import menus as menu_keys
from apps.core.roles import Role
from apps.ui.components.actions import Button
from apps.ui.components.data import EmptyState
from apps.ui.components.nav import FilterBar, Pagination
from apps.ui.views.pages import FormPage, ListPage, PortalPageView

PAGE_SIZE = 25


class NameListMixin:
    """Shared settings; subclasses set the model and the words for it."""

    portal = "admin"
    menu_key = menu_keys.INSTITUTE
    allowed_roles = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]
    model: type[NameList]
    noun = ""
    plural = ""
    url_prefix = ""

    def url(self, action: str, **kwargs: Any) -> str:
        return reverse(f"admin:{self.url_prefix}_{action}", kwargs=kwargs or None)


class NameRowObjectMixin(NameListMixin):
    """Load the row only after the access mixins have passed."""

    row: NameList

    def get_object(self) -> NameList:
        rows = self.model.objects.for_user(self.request.user)
        return get_object_or_404(rows, pk=self.kwargs["pk"])


class NameListPage(NameListMixin, ListPage):
    @property
    def title(self) -> str:
        return self.plural.capitalize()

    def get_search(self) -> str:
        return self.request.GET.get("q", "").strip()

    def get_actions(self) -> list[Any]:
        return [Button(f"Add {self.noun}", url=self.url("create"))]

    def get_components(self) -> dict[str, Any]:
        search = self.get_search()
        rows = list_name_rows(self.model, self.request.user, search)
        page = Paginator(rows, PAGE_SIZE).get_page(self.request.GET.get("page"))
        filter_field = {"name": "q", "label": "Search by name", "value": search}
        return {
            "filters": FilterBar(filters=[filter_field]),
            "table": self.get_table(list(page.object_list), search),
            "pagination": Pagination(
                page, query=urlencode({"q": search}) if search else ""
            ),
        }

    def get_table(self, rows: list[NameList], search: str) -> Any:
        if not rows and not search:
            return EmptyState(
                f"No {self.plural} yet.",
                action=Button(f"Add your first {self.noun}", url=self.url("create")),
            )
        return NameListTable(
            rows,
            url_prefix=self.url_prefix,
            empty_title=f"No {self.plural} match your search.",
        )


class NameRowFormPage(FormPage):
    """Create and edit pages map service errors back onto the form."""

    def get_form_kwargs(self) -> dict[str, Any]:
        return {"save_label": self.save_label, "cancel_url": self.url("list")}

    def form_valid(self, form: NameRowForm) -> HttpResponse:
        try:
            self.save(form.cleaned_data["name"])
        except ValidationError as error:
            for field, field_errors in error.message_dict.items():
                form.add_error(field, field_errors)
            return self.form_invalid(form)
        return HttpResponseRedirect(self.url("list"))


class NameRowCreatePage(NameListMixin, NameRowFormPage):
    form_class = NameRowForm

    @property
    def title(self) -> str:
        return f"Add {self.noun}"

    @property
    def save_label(self) -> str:
        return f"Add {self.noun}"

    def save(self, name: str) -> None:
        create_name_row(self.model, self.get_institute(), name=name, noun=self.noun)
        messages.success(self.request, f"{self.noun.capitalize()} added.")


class NameRowEditPage(NameRowObjectMixin, NameRowFormPage):
    form_class = NameRowForm
    save_label = "Save changes"

    @property
    def title(self) -> str:
        return f"Edit {self.noun}"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.row = self.get_object()
        return super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.row = self.get_object()
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self) -> dict[str, Any]:
        return {**super().get_form_kwargs(), "initial": {"name": self.row.name}}

    def get_actions(self) -> list[Any]:
        return [status_dialog(self.row, self.url_prefix)]

    def save(self, name: str) -> None:
        rename_name_row(self.row, name=name, noun=self.noun)
        messages.success(self.request, f"{self.noun.capitalize()} saved.")


class NameRowStatusView(NameRowObjectMixin, PortalPageView):
    """POST-only activate or deactivate, reached from the confirm dialog."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        row = self.get_object()
        action = request.POST.get("action")
        if action not in {"activate", "deactivate"}:
            messages.error(request, "Unknown action.")
        else:
            set_name_row_active(row, is_active=action == "activate")
            messages.success(request, f"{row.name} {action}d.")
        return HttpResponseRedirect(self.url("list"))


class ClassLabelMixin:
    model = ClassLabel
    noun = "class"
    plural = "classes"
    url_prefix = "class"


class BatchMixin:
    model = Batch
    noun = "batch"
    plural = "batches"
    url_prefix = "batch"


class SubjectMixin:
    model = Subject
    noun = "subject"
    plural = "subjects"
    url_prefix = "subject"


class ClassListPage(ClassLabelMixin, NameListPage):
    pass


class ClassCreatePage(ClassLabelMixin, NameRowCreatePage):
    pass


class ClassEditPage(ClassLabelMixin, NameRowEditPage):
    pass


class ClassStatusView(ClassLabelMixin, NameRowStatusView):
    pass


class BatchListPage(BatchMixin, NameListPage):
    pass


class BatchCreatePage(BatchMixin, NameRowCreatePage):
    pass


class BatchEditPage(BatchMixin, NameRowEditPage):
    pass


class BatchStatusView(BatchMixin, NameRowStatusView):
    pass


class SubjectListPage(SubjectMixin, NameListPage):
    pass


class SubjectCreatePage(SubjectMixin, NameRowCreatePage):
    pass


class SubjectEditPage(SubjectMixin, NameRowEditPage):
    pass


class SubjectStatusView(SubjectMixin, NameRowStatusView):
    pass
