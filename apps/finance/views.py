"""Fee pages (roadmap Phase 7)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import Batch
from apps.core import menus as menu_keys
from apps.core.query import id_param, search_param
from apps.core.roles import Role
from apps.finance.forms import ChallanConfirmForm, ChallanGenerateForm, FeePlanForm
from apps.finance.models import Challan, ChallanStatus, FeePlan
from apps.finance.pdf import challans_pdf
from apps.finance.services import (
    OVERDUE,
    cancel_challan,
    check_challan_dates,
    create_fee_plan,
    default_due_date,
    list_challans,
    list_fee_plans,
    month_start,
    preview_challans,
    set_fee_plan_active,
    update_fee_plan,
)
from apps.finance.tasks import queue_challans
from apps.finance.ui import (
    ChallanLineTable,
    ChallanTable,
    FeePlanTable,
    SkippedTable,
    challan_badge,
    challan_url,
    date_text,
    money,
    month_text,
)
from apps.people.models import ProfileStatus, StudentProfile
from apps.ui.components import (
    Button,
    ConfirmDialog,
    EmptyState,
    FilterBar,
    Pagination,
    SectionCard,
)
from apps.ui.components.data import DetailList
from apps.ui.components.forms import CrispyForm, PortalPostForm
from apps.ui.views.pages import DetailPage, FormPage, ListPage, PortalPageView

PAGE_SIZE = 25
CHALLAN_STATUS_OPTIONS = [
    ("", "Any status"),
    *ChallanStatus.choices,
    (OVERDUE, "Overdue"),
]


def who(student: Any) -> str:
    """Example: Bilal Example (STU-001)."""
    return f"{student} ({student.student_code})"


def parse_iso(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return None


def parse_month(value: str) -> date | None:
    """A month filter like 2026-10 (the browser's month field)."""
    return parse_iso(f"{value}-01") if value else None


ADMIN_ROLES = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]


# Fee plans (Institute menu, SPEC 3 and 4.4)


class FeePlanMixin:
    portal = "admin"
    menu_key = menu_keys.INSTITUTE
    feature_key = "fees"
    allowed_roles = ADMIN_ROLES

    def url(self, action: str, **kwargs: Any) -> str:
        return reverse(f"admin:fee_plan_{action}", kwargs=kwargs or None)

    def get_plan(self) -> FeePlan:
        rows = FeePlan.objects.for_user(self.request.user)
        return get_object_or_404(rows, pk=self.kwargs["pk"])


class FeePlanListPage(FeePlanMixin, ListPage):
    title = "Fee plans"

    def get_subtitle(self) -> str:
        return "Monthly fees. A student's challan adds up their plans, less discounts."

    def get_actions(self) -> list[Any]:
        return [Button("Add fee plan", url=self.url("create"), icon="plus")]

    def get_components(self) -> dict[str, Any]:
        search = search_param(self.request.GET.get("q"))
        rows = list_fee_plans(self.request.user, search)
        page = Paginator(rows, PAGE_SIZE).get_page(self.request.GET.get("page"))
        if not page.object_list and not search:
            table: Any = EmptyState(
                "No fee plans yet.",
                text="Add a plan such as Tuition, then give it to students.",
                action=Button("Add your first fee plan", url=self.url("create")),
                icon="coins",
            )
        else:
            table = FeePlanTable(list(page.object_list), institute=self.get_institute())
        return {
            "filters": FilterBar(
                [{"name": "q", "label": "Search by name", "value": search}]
            ),
            "table": table,
            "pagination": Pagination(
                page, query=urlencode({"q": search}) if search else ""
            ),
        }


class FeePlanFormPage(FeePlanMixin, FormPage):
    form_class = FeePlanForm

    def get_form_kwargs(self) -> dict[str, Any]:
        return {
            **super().get_form_kwargs(),
            "save_label": self.save_label,
            "cancel_url": self.url("list"),
        }

    def form_valid(self, form: FeePlanForm) -> HttpResponse:
        try:
            self.save(form.cleaned_data["name"], form.cleaned_data["amount"])
        except ValidationError as error:
            for field, errors in error.message_dict.items():
                form.add_error(field if field in form.fields else None, errors)
            return self.form_invalid(form)
        return HttpResponseRedirect(self.url("list"))


class FeePlanCreatePage(FeePlanFormPage):
    title = "Add fee plan"
    save_label = "Add fee plan"

    def save(self, name: str, amount: Any) -> None:
        create_fee_plan(self.get_institute(), name=name, amount=amount)
        messages.success(self.request, "Fee plan added.")


class FeePlanEditPage(FeePlanFormPage):
    title = "Edit fee plan"
    save_label = "Save changes"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.plan = self.get_plan()
        return super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.plan = self.get_plan()
        return super().post(request, *args, **kwargs)

    def get_subtitle(self) -> str:
        return "A new amount counts for challans made from now on."

    def get_initial(self) -> dict[str, Any]:
        return {"name": self.plan.name, "amount": self.plan.amount}

    def get_form_kwargs(self) -> dict[str, Any]:
        return {**super().get_form_kwargs(), "initial": self.get_initial()}

    def get_actions(self) -> list[Any]:
        url = self.url("status", pk=self.plan.pk)
        if self.plan.is_active:
            return [
                ConfirmDialog(
                    f"Deactivate {self.plan.name}? New students cannot get it; "
                    "students who have it keep it.",
                    "Deactivate",
                    url=url,
                    fields=[("action", "deactivate")],
                )
            ]
        return [
            ConfirmDialog(
                f"Activate {self.plan.name}? New students can get it again.",
                "Activate",
                url=url,
                variant="primary",
                fields=[("action", "activate")],
            )
        ]

    def save(self, name: str, amount: Any) -> None:
        update_fee_plan(self.plan, name=name, amount=amount)
        messages.success(self.request, "Fee plan saved.")


class FeePlanStatusView(FeePlanMixin, PortalPageView):
    """POST only, from the confirm dialog."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        plan = self.get_plan()
        action = request.POST.get("action")
        if action not in ("activate", "deactivate"):
            messages.error(request, "Unknown action.")
        else:
            set_fee_plan_active(plan, is_active=action == "activate")
            messages.success(request, f"{plan.name} {action}d.")
        return HttpResponseRedirect(self.url("list"))


# Challans (Finance menu, roadmap 7.2, SPEC 3 and 4.7)


class ChallanMixin:
    portal = "admin"
    menu_key = menu_keys.FINANCE
    feature_key = "fees"
    allowed_roles = ADMIN_ROLES

    def get_challan(self) -> Challan:
        rows = Challan.objects.for_user(self.request.user).select_related(
            "student__user"
        )
        return get_object_or_404(rows, pk=self.kwargs["pk"])


class ChallanGeneratePage(ChallanMixin, DetailPage):
    """Step 1: month, due date and students. Step 2: the preview with a tick
    per student and the skipped list; Generate queues the Celery task."""

    title = "Generate challans"

    def batches(self) -> Any:
        return (
            Batch.objects.for_user(self.request.user)
            .filter(is_active=True)
            .order_by("name")
        )

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        today = timezone.localdate()
        self.form = ChallanGenerateForm(
            initial={"month": month_start(today)},
            batches=self.batches(),
            cancel_url=reverse("admin:challan_list"),
        )
        self.preview = None
        return super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if "students" in request.POST or request.POST.get("step") == "confirm":
            return self.confirm(request)
        self.form = ChallanGenerateForm(
            request.POST,
            batches=self.batches(),
            cancel_url=reverse("admin:challan_list"),
        )
        self.preview = None
        if self.form.is_valid():
            data = self.form.cleaned_data
            month = month_start(data["month"])
            due = data["due_date"] or default_due_date(self.get_institute(), month)
            try:
                check_challan_dates(month, due, timezone.localdate())
            except ValidationError as error:
                for name, errors in error.message_dict.items():
                    self.form.add_error(name, errors)
            else:
                self.month, self.due = month, due
                self.preview = preview_challans(month, self.students(data))
        return self.render_to_response(self.get_context_data())

    def students(self, data: dict[str, Any]) -> list[Any]:
        rows = StudentProfile.objects.for_user(self.request.user).filter(
            status=ProfileStatus.ACTIVE
        )
        if data.get("scope") == "batch" and data.get("batch"):
            rows = rows.filter(batch_subjects__batch=data["batch"]).distinct()
        return list(rows.select_related("user").order_by("user__first_name", "pk"))

    def confirm(self, request: HttpRequest) -> HttpResponse:
        month = parse_iso(request.POST.get("month"))
        due = parse_iso(request.POST.get("due_date"))
        wanted = {id_param(value) for value in request.POST.getlist("students")}
        if month is None or due is None:
            messages.error(request, "Start again: the month or due date is missing.")
            return HttpResponseRedirect(request.path)
        students = StudentProfile.objects.for_user(request.user).filter(
            pk__in=[pk for pk in wanted if pk], status=ProfileStatus.ACTIVE
        )
        ids = [
            plan.student.pk for plan in preview_challans(month, list(students)).planned
        ]
        if not ids:
            messages.error(request, "No student to make a challan for.")
            return HttpResponseRedirect(request.path)
        try:
            check_challan_dates(month, due, timezone.localdate())
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
            return HttpResponseRedirect(request.path)
        queue_challans(self.get_institute(), month, due, ids)
        challans = "challan" if len(ids) == 1 else "challans"
        messages.success(
            request, f"Making {len(ids)} {challans} for {month_text(month)}."
        )
        query = urlencode({"month": f"{month:%Y-%m}"})
        return HttpResponseRedirect(f"{reverse('admin:challan_list')}?{query}")

    def get_subtitle(self) -> str:
        return "Each student's challan adds up their fee plans, less discounts."

    def get_primary_cards(self) -> list[Any]:
        cards = [
            SectionCard(
                title="Month and students",
                icon="file-plus",
                body=self.form_body(self.form),
            )
        ]
        if self.preview is not None:
            cards += self.preview_cards()
        return cards

    def form_body(self, form: Any) -> Any:
        form.helper.disable_csrf = True  # PortalPostForm adds the token
        return PortalPostForm(
            action=self.request.path, body=CrispyForm(form=form), framed=False
        )

    def preview_cards(self) -> list[Any]:
        institute = self.get_institute()
        planned = self.preview.planned
        total = sum((plan.amount for plan in planned), Decimal("0"))
        choices = [
            (
                plan.student.pk,
                f"{who(plan.student)}: {money(plan.amount, institute)}",
            )
            for plan in planned
        ]
        form = ChallanConfirmForm(
            initial={
                "month": self.month,
                "due_date": self.due,
                "students": [pk for pk, _ in choices],
            },
            choices=choices,
            cancel_url=reverse("admin:challan_list"),
        )
        title = (
            f"Preview: {len(planned)} challans for {month_text(self.month)}, "
            f"{money(total, institute)}, due {date_text(self.due)}"
        )
        cards = [
            SectionCard(title=title, icon="list-checks", body=self.form_body(form))
        ]
        if self.preview.skipped:
            cards.append(
                SectionCard(
                    title=f"Skipped: {len(self.preview.skipped)}",
                    icon="info",
                    body=SkippedTable(rows=self.preview.skipped),
                )
            )
        return cards


class ChallanListPage(ChallanMixin, ListPage):
    title = "Challan records"
    filter_keys = ("q", "month", "batch", "status")

    def get_actions(self) -> list[Any]:
        url = reverse("admin:challan_generate")
        query = self.request.GET.urlencode()
        print_url = reverse("admin:challan_print") + (f"?{query}" if query else "")
        return [
            Button(
                "Print these challans",
                url=print_url,
                variant="secondary",
                icon="download",
            ),
            Button("Generate challans", url=url, icon="file-plus"),
        ]

    def get_components(self) -> dict[str, Any]:
        params = self.request.GET
        filters = {key: search_param(params.get(key)) for key in self.filter_keys}
        month = parse_month(filters["month"])
        rows = list_challans(
            self.request.user,
            month=month,
            batch_id=id_param(filters["batch"]),
            status=filters["status"],
            search=filters["q"],
        )
        page = Paginator(rows, PAGE_SIZE).get_page(params.get("page"))
        query = urlencode({key: value for key, value in filters.items() if value})
        batches = Batch.objects.for_user(self.request.user).order_by("name")
        return {
            "filters": FilterBar(
                [
                    {
                        "name": "q",
                        "label": "Search",
                        "value": filters["q"],
                        "placeholder": "Challan no., name or ID",
                    },
                    {
                        "name": "month",
                        "label": "Month",
                        "value": filters["month"],
                        "input_type": "month",
                    },
                    {
                        "name": "batch",
                        "label": "Batch",
                        "value": filters["batch"],
                        "options": [
                            ("", "Any batch"),
                            *((str(b.pk), b.name) for b in batches),
                        ],
                    },
                    {
                        "name": "status",
                        "label": "Status",
                        "value": filters["status"],
                        "options": CHALLAN_STATUS_OPTIONS,
                    },
                ]
            ),
            "table": ChallanTable(
                list(page.object_list), institute=self.get_institute()
            ),
            "pagination": Pagination(page, query=query),
        }


class ChallanDetailPage(ChallanMixin, DetailPage):
    title = "Challan"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.challan = self.get_challan()
        self.title = self.challan.number
        return super().get(request, *args, **kwargs)

    def get_subtitle(self) -> str:
        challan = self.challan
        return f"{who(challan.student)}, {month_text(challan.month)}"

    def get_actions(self) -> list[Any]:
        challan = self.challan
        if challan.status == ChallanStatus.CANCELLED:
            return []
        print_button = Button(
            "Print challan",
            url=challan_url(challan, "pdf"),
            variant="secondary",
            icon="download",
        )
        if challan.paid > 0:
            return [print_button]
        return [
            print_button,
            ConfirmDialog(
                f"Cancel {challan.number}? It takes no payments after this.",
                "Cancel challan",
                url=challan_url(challan, "cancel"),
                trigger_label="Cancel challan",
                dismiss_label="Keep challan",
            ),
        ]

    def get_primary_cards(self) -> list[Any]:
        institute = self.get_institute()
        lines = ChallanLineTable(
            rows=list(self.challan.lines.all()), institute=institute
        )
        return [SectionCard(title="Fees", icon="receipt", body=lines)]

    def get_sidebar_cards(self) -> list[Any]:
        challan, institute = self.challan, self.get_institute()
        rows: list[tuple[str, Any]] = [
            ("Status", challan_badge(challan)),
            ("Month", month_text(challan.month)),
            ("Issued", date_text(challan.issue_date)),
            ("Due date", date_text(challan.due_date)),
            ("Amount", money(challan.amount, institute)),
        ]
        if challan.late_fee:
            rows.append(("Late fee", money(challan.late_fee, institute)))
        rows += [
            ("Paid", money(challan.paid, institute)),
            ("Due", money(challan.balance, institute)),
        ]
        return [SectionCard(title="Details", icon="list", body=DetailList(rows))]


class ChallanCancelView(ChallanMixin, PortalPageView):
    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        challan = self.get_challan()
        try:
            cancel_challan(challan)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, f"{challan.number} cancelled.")
        return HttpResponseRedirect(challan_url(challan))


PRINT_LIMIT = 300  # challans in one bulk PDF


def pdf_response(content: bytes, filename: str) -> HttpResponse:
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


def printable(rows: Any) -> list[Challan]:
    return list(
        rows.select_related("student__user", "student__class_label").prefetch_related(
            "lines", "student__batch_subjects__batch"
        )
    )


class ChallanPdfView(ChallanMixin, PortalPageView):
    """One challan as a PDF (SPEC 9.1: three copies on one page)."""

    http_method_names = ["get"]

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        challan = self.get_challan()
        rows = Challan.objects.for_user(request.user).filter(pk=challan.pk)
        content = challans_pdf(printable(rows), self.get_institute())
        return pdf_response(content, f"{challan.number}.pdf")


class ChallanPrintView(ChallanMixin, PortalPageView):
    """The challans of the current Challan records filters in one PDF, one
    per page (SPEC 9.1 bulk print). Cancelled challans are left out."""

    http_method_names = ["get"]

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        params = request.GET
        rows = list_challans(
            request.user,
            month=parse_month(search_param(params.get("month"))),
            batch_id=id_param(search_param(params.get("batch"))),
            status=search_param(params.get("status")),
            search=search_param(params.get("q")),
        ).exclude(status=ChallanStatus.CANCELLED)
        challans = printable(rows[:PRINT_LIMIT])
        if not challans:
            messages.error(request, "No challans to print for these filters.")
            return HttpResponseRedirect(
                f"{reverse('admin:challan_list')}?{params.urlencode()}"
            )
        return pdf_response(
            challans_pdf(challans, self.get_institute()), "challans.pdf"
        )
