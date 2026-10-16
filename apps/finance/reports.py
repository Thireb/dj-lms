"""Fee reports (roadmap 7.3c, SPEC 3 "Daily/Monthly/Yearly Reports": Date
or month, Challans, Billed, Collected, Discounts, Outstanding).

Assumed (SPEC has no definitions): Challans, Billed and Discounts count the
challans of the period (by issue date for daily rows, by the challan month
for monthly and yearly rows); Collected counts the payments made in the
period; Outstanding is what those challans still owe today. Cancelled
challans are left out.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncYear

from apps.finance.models import Challan, ChallanLine, ChallanStatus, Payment

KINDS = ("daily", "monthly", "yearly")
ZERO = Decimal("0")


@dataclass
class ReportRow:
    period: date
    challans: int = 0
    billed: Decimal = ZERO
    collected: Decimal = ZERO
    discounts: Decimal = ZERO
    outstanding: Decimal = ZERO


@dataclass
class Report:
    kind: str
    rows: list[ReportRow] = field(default_factory=list)

    @property
    def totals(self) -> ReportRow:
        total = ReportRow(period=date.min)
        for row in self.rows:
            total.challans += row.challans
            total.billed += row.billed
            total.collected += row.collected
            total.discounts += row.discounts
            total.outstanding += row.outstanding
        return total


def _trunc(kind: str, name: str) -> Any:
    return {"daily": TruncDay, "monthly": TruncMonth, "yearly": TruncYear}[kind](name)


def _key(kind: str, value: Any) -> date:
    day = value.date() if hasattr(value, "date") and callable(value.date) else value
    if kind == "monthly":
        return day.replace(day=1)
    if kind == "yearly":
        return day.replace(month=1, day=1)
    return day


def fee_report(
    user: Any, kind: str, start: date, end: date, *, batch_id: int | None = None
) -> Report:
    """One row per day, month or year between ``start`` and ``end``."""
    challan_date = "issue_date" if kind == "daily" else "month"
    challans = Challan.objects.for_user(user).exclude(status=ChallanStatus.CANCELLED)
    challans = challans.filter(**{f"{challan_date}__range": (start, end)})
    payments = Payment.objects.for_user(user).filter(paid_on__range=(start, end))
    lines = ChallanLine.objects.filter(challan__in=challans)
    if batch_id:
        in_batch = Q(student__batch_subjects__batch_id=batch_id)
        challans = challans.filter(in_batch).distinct()
        payments = payments.filter(in_batch).distinct()
        lines = ChallanLine.objects.filter(challan__in=challans)
    rows: dict[date, ReportRow] = {}

    def row(value: Any) -> ReportRow:
        key = _key(kind, value)
        return rows.setdefault(key, ReportRow(period=key))

    billed = F("amount") + F("late_fee")
    for item in (
        Challan.objects.filter(pk__in=challans.values("pk"))
        .annotate(period=_trunc(kind, challan_date))
        .values("period")
        .annotate(count=Count("pk"), billed=Sum(billed), owed=Sum(billed - F("paid")))
    ):
        target = row(item["period"])
        target.challans += item["count"]
        target.billed += item["billed"] or ZERO
        target.outstanding += item["owed"] or ZERO
    for item in (
        lines.annotate(period=_trunc(kind, f"challan__{challan_date}"))
        .values("period")
        .annotate(total=Sum("discount"))
    ):
        row(item["period"]).discounts += item["total"] or ZERO
    for item in (
        Payment.objects.filter(pk__in=payments.values("pk"))
        .annotate(period=_trunc(kind, "paid_on"))
        .values("period")
        .annotate(total=Sum("amount"))
    ):
        row(item["period"]).collected += item["total"] or ZERO
    return Report(kind, [rows[key] for key in sorted(rows, reverse=True)])


def period_text(kind: str, period: date) -> str:
    if kind == "yearly":
        return str(period.year)
    if kind == "monthly":
        return f"{period:%b %Y}"
    return f"{period:%a} {period.day} {period:%b %Y}"


def csv_cell(value: Any) -> str:
    """Text a spreadsheet will not run as a formula (CSV injection)."""
    text = str(value)
    return f"'{text}" if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def report_csv(report: Report) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    label = {"daily": "Date", "monthly": "Month", "yearly": "Year"}[report.kind]
    writer.writerow(
        [label, "Challans", "Billed", "Collected", "Discounts", "Outstanding"]
    )
    for row in [*report.rows]:
        writer.writerow(
            [
                period_text(report.kind, row.period),
                row.challans,
                row.billed,
                row.collected,
                row.discounts,
                row.outstanding,
            ]
        )
    total = report.totals
    writer.writerow(
        [
            "Total",
            total.challans,
            total.billed,
            total.collected,
            total.discounts,
            total.outstanding,
        ]
    )
    return out.getvalue()
