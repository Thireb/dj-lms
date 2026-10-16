"""Finance components (Phase 7)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.urls import reverse

from apps.ui.components import Badge, Column, ConfirmDialog, DataTable
from apps.ui.components.actions import IconButton
from apps.ui.components.base import Component
from apps.ui.components.block_stack import ButtonRow
from apps.ui.safe_url import safe_url


def money(amount: Decimal | None, institute: Any) -> str:
    """Example: Rs 4,500 or Rs 4,500.50 (the institute's currency symbol)."""
    if amount is None:
        return "-"
    symbol = getattr(institute, "currency_symbol", "") or ""
    text = f"{amount:,.2f}"
    if text.endswith(".00"):
        text = text[:-3]
    return f"{symbol} {text}".strip()


class FeePlanTable(DataTable):
    """Fee Plans (SPEC 3): Name, Amount, Students count, Status."""

    empty_title = "No fee plans match your search."

    def __init__(self, rows, institute, **props):
        self.institute = institute
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("name", "Name", lambda plan: plan.name),
            Column("amount", "Amount", lambda plan: money(plan.amount, self.institute)),
            Column("students", "Students", lambda plan: str(plan.student_count)),
            Column("status", "Status", self.status),
            Column("actions", "", self.edit_button),
        ]

    def status(self, plan) -> Badge:
        if plan.is_active:
            return Badge("Active", tone="success")
        return Badge("Inactive", tone="neutral")

    def edit_button(self, plan) -> IconButton:
        url = reverse("admin:fee_plan_edit", kwargs={"pk": plan.pk})
        return IconButton("square-pen", f"Edit {plan.name}", url=url)


# Challans (roadmap 7.2)

STATUS_TONES = {  # SPEC 2: amber, blue, green, grey; overdue red
    "pending": "warning",
    "partial": "info",
    "paid": "success",
    "cancelled": "neutral",
}


def challan_badge(challan, today=None) -> Badge:
    from apps.finance.services import is_overdue

    if is_overdue(challan, today):
        return Badge("Overdue", tone="danger")
    return Badge(challan.get_status_display(), tone=STATUS_TONES[challan.status])


def month_text(month) -> str:
    """Example: Oct 2026."""
    return f"{month:%b %Y}"


def date_text(day) -> str:
    """Example: Sat 10 Oct 2026."""
    return f"{day:%a} {day.day} {day:%b %Y}"


def challan_url(challan, action: str = "detail") -> str:
    return reverse(f"admin:challan_{action}", kwargs={"pk": challan.pk})


class ChallanTable(DataTable):
    """Challan Records (SPEC 3): Challan no., Student, Month, Amount, Paid,
    Due, Due date, Status."""

    empty_title = "No challans match these filters."

    def __init__(self, rows, institute, **props):
        self.institute = institute
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        cash = self.money
        return [
            Column("number", "Challan no.", lambda c: c.number),
            Column(
                "student",
                "Student",
                lambda c: f"{c.student} ({c.student.student_code})",
            ),
            Column("month", "Month", lambda c: month_text(c.month)),
            Column("amount", "Amount", lambda c: cash(c.total)),
            Column("paid", "Paid", lambda c: cash(c.paid)),
            Column("due", "Due", lambda c: cash(c.balance)),
            Column("due_date", "Due date", lambda c: date_text(c.due_date)),
            Column("status", "Status", challan_badge),
            Column("actions", "", self.open_button),
        ]

    def money(self, amount) -> str:
        return money(amount, self.institute)

    def open_button(self, challan) -> IconButton:
        return IconButton("eye", f"View {challan.number}", url=challan_url(challan))


class ChallanLineTable(DataTable):
    """The fee plan lines of a challan (SPEC 9.1)."""

    empty_title = "No lines."

    def __init__(self, rows, institute, **props):
        self.institute = institute
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("name", "Fee", lambda line: line.name),
            Column("amount", "Amount", lambda line: money(line.amount, self.institute)),
            Column(
                "discount",
                "Discount",
                lambda line: money(line.discount, self.institute),
            ),
            Column("net", "Payable", lambda line: money(line.net, self.institute)),
        ]


class SkippedTable(DataTable):
    """Students the generation skips, and why (SPEC 4.7)."""

    empty_title = "No one is skipped."

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column(
                "student", "Student", lambda row: f"{row[0]} ({row[0].student_code})"
            ),
            Column("why", "Why", lambda row: row[1]),
        ]


# Payments (roadmap 7.3)


def payment_url(payment, action: str = "receipt") -> str:
    return reverse(f"admin:payment_{action}", kwargs={"pk": payment.pk})


class PayTable(ChallanTable):
    """Process payment: open challans with "Record payment"."""

    empty_title = "No open challans match. Search by challan no., name or ID."

    def open_button(self, challan) -> IconButton:
        label = f"Record payment for {challan.number}"
        return IconButton("banknote", label, url=challan_url(challan, "pay"))


class PaymentTable(DataTable):
    """Payments: Receipt no., Date, Challan no., Amount, Method, Reference,
    Received by, and the receipt PDF."""

    empty_title = "No payments yet."

    def __init__(self, rows, institute, **props):
        self.institute = institute
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("number", "Receipt no.", lambda p: p.number),
            Column("date", "Date", lambda p: date_text(p.paid_on)),
            Column("challan", "Challan no.", lambda p: p.challan.number),
            Column("amount", "Amount", lambda p: money(p.amount, self.institute)),
            Column("method", "Method", lambda p: p.get_method_display()),
            Column("reference", "Reference", lambda p: p.reference or "-"),
            Column("by", "Received by", self.received_by),
            Column("actions", "", self.receipt_button),
        ]

    def received_by(self, payment) -> str:
        user = payment.received_by
        return (user.get_full_name() or user.email) if user else "-"

    def receipt_button(self, payment) -> IconButton:
        return IconButton(
            "download", f"Receipt {payment.number}", url=payment_url(payment)
        )


# Receipts (roadmap 7.3b)

RECEIPT_TONES = {"waiting": "warning", "approved": "success", "rejected": "danger"}


def receipt_badge(receipt) -> Badge:
    return Badge(receipt.get_status_display(), tone=RECEIPT_TONES[receipt.status])


def months_of(receipt) -> str:
    return ", ".join(month_text(challan.month) for challan in receipt.challans.all())


class ReceiptInboxTable(DataTable):
    """Receipt Inbox (SPEC 3): Submitted on, Student, Guardian, Months,
    Amount, Reference, Status."""

    empty_title = "No receipts match these filters."

    def __init__(self, rows, institute, **props):
        self.institute = institute
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column(
                "submitted", "Submitted on", lambda r: date_text(r.created_at.date())
            ),
            Column(
                "student",
                "Student",
                lambda r: f"{r.student} ({r.student.student_code})",
            ),
            Column("guardian", "Guardian", self.guardian),
            Column("months", "Months", months_of),
            Column("amount", "Amount", lambda r: money(r.amount, self.institute)),
            Column("reference", "Reference", lambda r: r.reference or "-"),
            Column("status", "Status", receipt_badge),
            Column("actions", "", self.open_button),
        ]

    def guardian(self, receipt) -> str:
        user = receipt.submitted_by
        return (user.get_full_name() or user.email) if user else "-"

    def open_button(self, receipt) -> IconButton:
        url = reverse("admin:receipt_detail", kwargs={"pk": receipt.pk})
        return IconButton("eye", f"View {receipt.number}", url=url)


class GuardianReceiptTable(DataTable):
    """Fee pay history (SPEC 3 Guardian: "a history list of submissions with
    status")."""

    empty_title = "No receipts sent yet."

    def __init__(self, rows, institute, **props):
        self.institute = institute
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("number", "Receipt", lambda r: r.number),
            Column("submitted", "Sent on", lambda r: date_text(r.created_at.date())),
            Column("months", "Months", months_of),
            Column("amount", "Amount", lambda r: money(r.amount, self.institute)),
            Column("status", "Status", receipt_badge),
            Column("reason", "Note", lambda r: r.reason or "-"),
            Column("actions", "", self.file_button),
        ]

    def file_button(self, receipt) -> IconButton:
        url = reverse("guardian:receipt_file", kwargs={"pk": receipt.pk})
        return IconButton("file", f"Open {receipt.number}", url=url, new_tab=True)


class ReceiptImage(Component):
    """A receipt photo on the admin page, loaded from the checked file view
    (never a public URL)."""

    template_name = "finance/receipt_image.html"

    def __init__(self, url, alt, **props):
        super().__init__(url=safe_url(url), alt=alt, **props)


# Reports (roadmap 7.3c)


class ReportTable(DataTable):
    """Daily, monthly or yearly fees (SPEC 3), with a Total row."""

    empty_title = "No challans or payments in these dates."

    def __init__(self, report, institute, **props):
        from apps.finance.reports import period_text

        self.institute, self.kind = institute, report.kind
        rows = [(period_text(report.kind, row.period), row) for row in report.rows]
        if report.rows:
            rows.append(("Total", report.totals))
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        label = {"daily": "Date", "monthly": "Month", "yearly": "Year"}[self.kind]
        cash = lambda value: money(value, self.institute)  # noqa: E731
        return [
            Column("period", label, lambda item: item[0]),
            Column("challans", "Challans", lambda item: str(item[1].challans)),
            Column("billed", "Billed", lambda item: cash(item[1].billed)),
            Column("collected", "Collected", lambda item: cash(item[1].collected)),
            Column("discounts", "Discounts", lambda item: cash(item[1].discounts)),
            Column(
                "outstanding", "Outstanding", lambda item: cash(item[1].outstanding)
            ),
        ]


# Fee defaulters (roadmap 7.3c)


class DefaulterTable(DataTable):
    """SPEC 3: Student, Guardian, Phone, Unpaid months, Total due, Oldest
    due date, Portal blocked; Message guardian and Block / Unblock."""

    empty_title = "No defaulters. Every challan is paid or within its grace days."

    def __init__(self, rows, institute, back_url, can_message, can_block, **props):
        self.institute, self.back_url = institute, back_url
        self.can_message, self.can_block = can_message, can_block
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column(
                "student",
                "Student",
                lambda r: f"{r.student} ({r.student.student_code})",
            ),
            Column("guardian", "Guardian", self.guardian),
            Column("phone", "Phone", lambda r: r.phone or "-"),
            Column("months", "Unpaid months", lambda r: str(r.unpaid_months)),
            Column("due", "Total due", lambda r: money(r.total_due, self.institute)),
            Column("oldest", "Oldest due date", lambda r: date_text(r.oldest_due)),
            Column("blocked", "Portal blocked", self.blocked),
            Column("actions", "", self.actions),
        ]

    def guardian(self, row) -> str:
        return (
            (row.guardian.get_full_name() or row.guardian.email)
            if row.guardian
            else "-"
        )

    def blocked(self, row) -> Badge:
        return (
            Badge("Blocked", tone="danger")
            if row.blocked
            else Badge("No", tone="neutral")
        )

    def actions(self, row) -> Any:
        items: list[Any] = []
        if self.can_message and row.guardian is not None:
            url = f"{reverse('admin:message_compose')}?to={row.guardian.pk}"
            items.append(
                IconButton("mail", f"Message the guardian of {row.student}", url=url)
            )
        if self.can_block:
            action = "unblock" if row.blocked else "block"
            items.append(
                ConfirmDialog(
                    f"{action.capitalize()} the student portal of {row.student}?",
                    action.capitalize(),
                    url=reverse(
                        "admin:portal_access_action", kwargs={"pk": row.student.pk}
                    ),
                    trigger_label=action.capitalize(),
                    variant="danger" if action == "block" else "primary",
                    fields=[("action", action), ("next", self.back_url)],
                )
            )
        return ButtonRow(items=items)


# Student Fee details and guardian Fee and challans (roadmap 7.5)


class OwnChallanTable(DataTable):
    """SPEC 3: Challan no., Month, Amount, Paid, Due date, Status; the
    guardian list adds Print."""

    empty_title = "No challans yet."

    def __init__(self, rows, institute, print_url=None, **props):
        self.institute, self.print_url = institute, print_url
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        columns = [
            Column("number", "Challan no.", lambda c: c.number),
            Column("month", "Month", lambda c: month_text(c.month)),
            Column("amount", "Amount", lambda c: money(c.total, self.institute)),
            Column("paid", "Paid", lambda c: money(c.paid, self.institute)),
            Column("due_date", "Due date", lambda c: date_text(c.due_date)),
            Column("status", "Status", challan_badge),
        ]
        if self.print_url is not None:
            columns.append(Column("actions", "", self.print_button))
        return columns

    def print_button(self, challan) -> IconButton:
        return IconButton(
            "download", f"Print {challan.number}", url=self.print_url(challan)
        )
