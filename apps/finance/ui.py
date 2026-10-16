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
