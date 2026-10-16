"""Finance components (Phase 7)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.urls import reverse

from apps.ui.components import Badge, Column, DataTable
from apps.ui.components.actions import IconButton


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
