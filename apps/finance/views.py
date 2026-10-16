"""Fee pages (roadmap Phase 7)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import Batch
from apps.core import menus as menu_keys
from apps.core.query import id_param, search_param
from apps.core.roles import Role
from apps.finance.forms import (
    ChallanConfirmForm,
    ChallanGenerateForm,
    FeePlanForm,
    PaymentForm,
    ReceiptForm,
    RejectReceiptForm,
)
from apps.finance.models import (
    Challan,
    ChallanStatus,
    FeePlan,
    Payment,
    PaymentMethod,
    ReceiptStatus,
    ReceiptSubmission,
)
from apps.finance.pdf import challans_pdf, receipt_pdf
from apps.finance.receipts import (
    approve_receipt,
    open_challans_of,
    reject_receipt,
    submit_receipt,
)
from apps.finance.services import (
    OVERDUE,
    cancel_challan,
    check_challan_dates,
    create_fee_plan,
    default_due_date,
    fee_history,
    list_challans,
    list_fee_plans,
    month_start,
    open_challans,
    preview_challans,
    record_payment,
    set_fee_plan_active,
    update_fee_plan,
)
from apps.finance.tasks import queue_challans
from apps.finance.ui import (
    ChallanLineTable,
    ChallanTable,
    FeePlanTable,
    GuardianReceiptTable,
    PaymentTable,
    PayTable,
    ReceiptImage,
    ReceiptInboxTable,
    SkippedTable,
    challan_badge,
    challan_url,
    date_text,
    money,
    month_text,
    receipt_badge,
)
from apps.people.models import ProfileStatus, StudentProfile
from apps.people.views import GuardianChildMixin
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
        actions: list[Any] = [print_button]
        if challan.balance > 0:
            pay = Button(
                "Record payment", url=challan_url(challan, "pay"), icon="banknote"
            )
            actions.append(pay)
        if challan.paid > 0:
            return actions
        return [
            *actions,
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
        payments = self.challan.payments.select_related("challan", "received_by")
        return [
            SectionCard(title="Fees", icon="receipt", body=lines),
            SectionCard(
                title="Payments",
                icon="banknote",
                body=PaymentTable(list(payments), institute=institute),
            ),
        ]

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
        history = reverse(
            "admin:student_fee_history", kwargs={"pk": challan.student_id}
        )
        rows.append(("Student", Button("Fee history", url=history, variant="ghost")))
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


# Payments (Finance menu, roadmap 7.3, SPEC 4.8)


class PaymentProcessPage(ChallanMixin, ListPage):
    """Search a challan or student, then Record payment (SPEC 4.8)."""

    title = "Process payment"

    def get_subtitle(self) -> str:
        return "Find the challan by its number, the student's name or ID."

    def get_components(self) -> dict[str, Any]:
        search = search_param(self.request.GET.get("q"))
        rows = (
            open_challans(self.request.user, search)
            if search
            else Challan.objects.none()
        )
        page = Paginator(rows, PAGE_SIZE).get_page(self.request.GET.get("page"))
        table: Any = (
            PayTable(list(page.object_list), institute=self.get_institute())
            if search
            else EmptyState(
                "Search to start.",
                text="Pending and partly paid challans show here.",
                icon="search",
            )
        )
        return {
            "filters": FilterBar(
                [
                    {
                        "name": "q",
                        "label": "Challan or student",
                        "value": search,
                        "placeholder": "Challan no., name or ID",
                    }
                ]
            ),
            "table": table,
            "pagination": Pagination(
                page, query=urlencode({"q": search}) if search else ""
            ),
        }


class ChallanPayPage(ChallanMixin, FormPage):
    """Record a payment against one challan."""

    title = "Record payment"
    form_class = PaymentForm

    def dispatch_challan(self) -> None:
        self.challan = self.get_challan()

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.dispatch_challan()
        if self.challan.status in (ChallanStatus.PAID, ChallanStatus.CANCELLED):
            messages.info(request, f"{self.challan.number} has nothing to pay.")
            return HttpResponseRedirect(challan_url(self.challan))
        return super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.dispatch_challan()
        return super().post(request, *args, **kwargs)

    def get_subtitle(self) -> str:
        challan, institute = self.challan, self.get_institute()
        return (
            f"{challan.number}, {who(challan.student)}, {month_text(challan.month)}: "
            f"balance {money(challan.balance, institute)}."
        )

    def get_form_kwargs(self) -> dict[str, Any]:
        return {
            **super().get_form_kwargs(),
            "cancel_url": challan_url(self.challan),
            "initial": {
                "amount": self.challan.balance,
                "paid_on": timezone.localdate(),
                "method": PaymentMethod.CASH,
            },
        }

    def form_valid(self, form: PaymentForm) -> HttpResponse:
        data = form.cleaned_data
        try:
            payment = record_payment(
                self.challan,
                amount=data["amount"],
                paid_on=data["paid_on"],
                method=data["method"],
                reference=data["reference"],
                note=data["note"],
                by=self.request.user,
            )
        except ValidationError as error:
            if hasattr(error, "error_dict"):
                for name, errors in error.message_dict.items():
                    form.add_error(name if name in form.fields else None, errors)
            else:
                form.add_error(None, error)
            return self.form_invalid(form)
        amount = money(payment.amount, self.get_institute())
        messages.success(
            self.request, f"Payment {payment.number} of {amount} recorded."
        )
        return HttpResponseRedirect(challan_url(self.challan))


class PaymentReceiptView(ChallanMixin, PortalPageView):
    """The payment receipt PDF (SPEC 9.3)."""

    http_method_names = ["get"]

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        rows = Payment.objects.for_user(request.user).select_related(
            "challan", "student__user", "received_by"
        )
        payment = get_object_or_404(rows, pk=self.kwargs["pk"])
        content = receipt_pdf(payment, self.get_institute())
        return pdf_response(content, f"{payment.number}.pdf")


class StudentFeeHistoryPage(ChallanMixin, DetailPage):
    """One student's challans and payments, with the totals (roadmap 7.3)."""

    title = "Fee history"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        rows = StudentProfile.objects.for_user(request.user).select_related("user")
        self.student = get_object_or_404(rows, pk=self.kwargs["pk"])
        self.history = fee_history(self.student)
        self.title = f"Fee history: {self.student}"
        return super().get(request, *args, **kwargs)

    def get_subtitle(self) -> str:
        return who(self.student)

    def get_primary_cards(self) -> list[Any]:
        institute = self.get_institute()
        return [
            SectionCard(
                title="Challans",
                icon="receipt-text",
                body=ChallanTable(self.history.challans, institute=institute),
            ),
            SectionCard(
                title="Payments",
                icon="banknote",
                body=PaymentTable(self.history.payments, institute=institute),
            ),
        ]

    def get_sidebar_cards(self) -> list[Any]:
        history, institute = self.history, self.get_institute()
        rows = [
            ("Billed", money(history.billed, institute)),
            ("Paid", money(history.paid, institute)),
            ("Due", money(history.due, institute)),
        ]
        return [SectionCard(title="Totals", icon="list", body=DetailList(rows))]


# Receipts (roadmap 7.3b): guardian Fee pay, admin Receipt inbox

CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def receipt_file_response(receipt: ReceiptSubmission) -> HttpResponse:
    """Stream a private receipt file. Shown in the browser, never sniffed
    as another type, never cached by a shared cache."""
    suffix = Path(receipt.file.name).suffix.lower()
    response = FileResponse(
        receipt.file.open("rb"),
        content_type=CONTENT_TYPES.get(suffix, "application/octet-stream"),
        as_attachment=False,
        filename=f"{receipt.number}{suffix}",
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


class GuardianFeeMixin(GuardianChildMixin):
    portal = "guardian"
    feature_key = "fees"
    allowed_roles = [Role.GUARDIAN]


class GuardianFeePayPage(GuardianFeeMixin, DetailPage):
    """SPEC 3 Guardian Fee Pay: the form (SPEC 4.17) and the history of
    sent receipts with their status."""

    title = "Fee pay"
    active_item = "fee_pay"

    def load(self) -> None:
        self.open = open_challans_of(self.child) if self.child else []

    def make_form(self, data: Any = None, files: Any = None) -> ReceiptForm:
        institute = self.get_institute()
        choices = [
            (c.pk, f"{c.number}, {month_text(c.month)}: {money(c.balance, institute)}")
            for c in self.open
        ]
        total = sum((c.balance for c in self.open), Decimal("0"))
        return ReceiptForm(
            data,
            files,
            choices=choices,
            cancel_url=reverse("guardian:home"),
            initial={
                "challans": [pk for pk, _ in choices],
                "amount": total or None,
                "paid_on": timezone.localdate(),
            },
        )

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.load()
        self.form = self.make_form()
        return super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.load()
        if self.child is None:
            return HttpResponseRedirect(request.path)
        self.form = self.make_form(request.POST, request.FILES)
        if self.form.is_valid():
            data = self.form.cleaned_data
            by_pk = {challan.pk: challan for challan in self.open}
            try:
                receipt = submit_receipt(
                    request.user,
                    self.child,
                    challans=[by_pk[pk] for pk in data["challans"] if pk in by_pk],
                    amount=data["amount"],
                    paid_on=data["paid_on"],
                    reference=data["reference"],
                    upload=data["file"],
                )
            except ValidationError as error:
                if hasattr(error, "error_dict"):
                    for name, errors in error.message_dict.items():
                        target = name if name in self.form.fields else None
                        self.form.add_error(target, errors)
                else:
                    self.form.add_error(None, error)
            else:
                if receipt.status == ReceiptStatus.APPROVED:
                    messages.success(
                        request, f"Receipt {receipt.number} sent and approved."
                    )
                else:
                    messages.success(
                        request,
                        f"Receipt {receipt.number} sent. The office checks it soon.",
                    )
                return HttpResponseRedirect(request.path)
        return self.render_to_response(self.get_context_data())

    def get_subtitle(self) -> str:
        if self.child is None:
            return ""
        return f"Send proof of a payment for {self.child}."

    def get_primary_cards(self) -> list[Any]:
        if self.child is None:
            return [
                EmptyState(
                    "No children are linked to this account yet.",
                    text="Contact the institute office.",
                    icon="graduation-cap",
                )
            ]
        institute = self.get_institute()
        history = ReceiptSubmission.objects.for_user(self.request.user).filter(
            student=self.child
        )
        cards: list[Any] = []
        if self.open:
            self.form.helper.disable_csrf = True  # PortalPostForm adds the token
            form = PortalPostForm(
                action=self.request.path, body=CrispyForm(form=self.form), framed=False
            )
            cards.append(SectionCard(title="Send a receipt", icon="upload", body=form))
        else:
            cards.append(
                SectionCard(
                    title="Send a receipt",
                    icon="upload",
                    body=EmptyState(
                        "Nothing to pay.", text="No challan is open.", icon="check"
                    ),
                )
            )
        cards.append(
            SectionCard(
                title="Receipts you sent",
                icon="list",
                body=GuardianReceiptTable(
                    list(history.prefetch_related("challans")), institute=institute
                ),
            )
        )
        return cards


class GuardianReceiptFileView(GuardianFeeMixin, PortalPageView):
    http_method_names = ["get"]

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        rows = ReceiptSubmission.objects.for_user(request.user)
        return receipt_file_response(get_object_or_404(rows, pk=self.kwargs["pk"]))


class ReceiptMixin(ChallanMixin):
    def get_receipt(self) -> ReceiptSubmission:
        rows = ReceiptSubmission.objects.for_user(self.request.user).select_related(
            "student__user", "submitted_by", "reviewed_by"
        )
        return get_object_or_404(rows, pk=self.kwargs["pk"])


class ReceiptInboxPage(ReceiptMixin, ListPage):
    """SPEC 3 Receipt Inbox, with the status and date range filters."""

    title = "Receipt inbox"
    filter_keys = ("status", "from", "to")

    def get_subtitle(self) -> str:
        return "Receipts guardians sent. Approve to record the payments."

    def get_components(self) -> dict[str, Any]:
        params = self.request.GET
        filters = {key: search_param(params.get(key)) for key in self.filter_keys}
        status = filters["status"] if filters["status"] in ReceiptStatus.values else ""
        rows = ReceiptSubmission.objects.for_user(self.request.user)
        if status:
            rows = rows.filter(status=status)
        start, end = parse_iso(filters["from"]), parse_iso(filters["to"])
        if start:
            rows = rows.filter(created_at__date__gte=start)
        if end:
            rows = rows.filter(created_at__date__lte=end)
        rows = rows.select_related("student__user", "submitted_by").prefetch_related(
            "challans"
        )
        page = Paginator(rows, PAGE_SIZE).get_page(params.get("page"))
        query = urlencode({key: value for key, value in filters.items() if value})
        return {
            "filters": FilterBar(
                [
                    {
                        "name": "status",
                        "label": "Status",
                        "value": status,
                        "options": [("", "Any status"), *ReceiptStatus.choices],
                    },
                    {
                        "name": "from",
                        "label": "From",
                        "value": filters["from"],
                        "input_type": "date",
                    },
                    {
                        "name": "to",
                        "label": "To",
                        "value": filters["to"],
                        "input_type": "date",
                    },
                ]
            ),
            "table": ReceiptInboxTable(
                list(page.object_list), institute=self.get_institute()
            ),
            "pagination": Pagination(page, query=query),
        }


class ReceiptDetailPage(ReceiptMixin, DetailPage):
    """One receipt: the file, the challans it pays, Approve and Reject."""

    title = "Receipt"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.receipt = self.get_receipt()
        self.title = self.receipt.number
        self.form = RejectReceiptForm()
        return super().get(request, *args, **kwargs)

    def get_subtitle(self) -> str:
        sent = date_text(self.receipt.created_at.date())
        return f"{who(self.receipt.student)}, sent {sent}"

    def file_url(self) -> str:
        return reverse("admin:receipt_file", kwargs={"pk": self.receipt.pk})

    def get_actions(self) -> list[Any]:
        actions: list[Any] = [
            Button(
                "Open the file",
                url=self.file_url(),
                variant="secondary",
                icon="file",
                new_tab=True,
            )
        ]
        if self.receipt.status == ReceiptStatus.WAITING:
            actions.append(
                ConfirmDialog(
                    "Approve this receipt? The payments are recorded on the challans, "
                    "oldest first.",
                    "Approve",
                    url=reverse(
                        "admin:receipt_approve", kwargs={"pk": self.receipt.pk}
                    ),
                    trigger_label="Approve",
                    variant="primary",
                )
            )
        return actions

    def get_primary_cards(self) -> list[Any]:
        receipt, institute = self.receipt, self.get_institute()
        cards: list[Any] = []
        if Path(receipt.file.name).suffix.lower() != ".pdf":
            cards.append(
                SectionCard(
                    title="Receipt",
                    icon="file",
                    body=ReceiptImage(self.file_url(), f"Receipt {receipt.number}"),
                )
            )
        challans = list(receipt.challans.select_related("student__user"))
        cards.append(
            SectionCard(
                title="Challans it pays",
                icon="receipt-text",
                body=ChallanTable(challans, institute=institute),
            )
        )
        if receipt.status == ReceiptStatus.WAITING:
            self.form.helper.disable_csrf = True  # PortalPostForm adds the token
            url = reverse("admin:receipt_reject", kwargs={"pk": receipt.pk})
            cards.append(
                SectionCard(
                    title="Reject",
                    icon="x",
                    body=PortalPostForm(
                        action=url, body=CrispyForm(form=self.form), framed=False
                    ),
                )
            )
        return cards

    def get_sidebar_cards(self) -> list[Any]:
        receipt, institute = self.receipt, self.get_institute()
        user = receipt.submitted_by
        rows: list[tuple[str, Any]] = [
            ("Status", receipt_badge(receipt)),
            ("Amount", money(receipt.amount, institute)),
            ("Paid on", date_text(receipt.paid_on)),
            ("Reference", receipt.reference or "-"),
            ("Guardian", (user.get_full_name() or user.email) if user else "-"),
        ]
        if receipt.reason:
            rows.append(("Reason", receipt.reason))
        return [SectionCard(title="Details", icon="list", body=DetailList(rows))]


class ReceiptApproveView(ReceiptMixin, PortalPageView):
    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        receipt = self.get_receipt()
        try:
            approve_receipt(receipt, by=request.user)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(
                request, f"{receipt.number} approved. The payments are recorded."
            )
        return HttpResponseRedirect(
            reverse("admin:receipt_detail", kwargs={"pk": receipt.pk})
        )


class ReceiptRejectView(ReceiptMixin, PortalPageView):
    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        receipt = self.get_receipt()
        form = RejectReceiptForm(request.POST)
        reason = form.cleaned_data["reason"] if form.is_valid() else ""
        try:
            reject_receipt(receipt, reason=reason, by=request.user)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, f"{receipt.number} rejected.")
        return HttpResponseRedirect(
            reverse("admin:receipt_detail", kwargs={"pk": receipt.pk})
        )


class AdminReceiptFileView(ReceiptMixin, PortalPageView):
    http_method_names = ["get"]

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return receipt_file_response(self.get_receipt())
