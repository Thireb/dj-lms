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

from django.db.models import Count, F, Min, Q, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncYear

from apps.finance.models import Challan, ChallanLine, ChallanStatus, Payment
from apps.people.models import StudentProfile

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


# Fee defaulters (SPEC 3: Student, Guardian, Phone, Unpaid months, Total
# due, Oldest due date, Portal blocked; SPEC 6.1: overdue longer than the
# grace days)


@dataclass(frozen=True)
class DefaulterRow:
    student: Any
    guardian: Any  # the first linked guardian's user, or None
    phone: str
    unpaid_months: int
    total_due: Decimal
    oldest_due: date
    blocked: bool


def defaulter_cutoff(institute: Any, today: date) -> date:
    """A challan due before this date is a defaulter's (overdue longer than
    the grace days)."""
    from datetime import timedelta

    return today - timedelta(days=institute.settings.grace_days_after_due)


def defaulters(
    user: Any,
    institute: Any,
    today: date,
    *,
    batch_id: int | None = None,
    min_amount: Decimal | None = None,
) -> list[DefaulterRow]:
    from apps.people.models import GuardianStudentLink, PortalAccessRule

    challans = Challan.objects.for_user(user).filter(
        status__in=[ChallanStatus.PENDING, ChallanStatus.PARTIAL],
        due_date__lt=defaulter_cutoff(institute, today),
    )
    if batch_id:
        challans = challans.filter(student__batch_subjects__batch_id=batch_id)
    groups = (
        Challan.objects.filter(pk__in=challans.values("pk"))
        .values("student_id")
        .annotate(
            months=Count("pk"),
            due=Sum(F("amount") + F("late_fee") - F("paid")),
            oldest=Min("due_date"),
        )
    )
    if min_amount:
        groups = groups.filter(due__gte=min_amount)
    groups = list(groups)
    ids = [group["student_id"] for group in groups]
    students = {
        student.pk: student
        for student in StudentProfile.objects.filter(pk__in=ids).select_related("user")
    }
    guardians: dict[int, Any] = {}
    for link in (
        GuardianStudentLink.objects.filter(student_id__in=ids)
        .select_related("guardian__user")
        .order_by("pk")
    ):
        guardians.setdefault(link.student_id, link.guardian.user)
    blocked = set(
        PortalAccessRule.objects.filter(student_id__in=ids, blocked=True).values_list(
            "student_id", flat=True
        )
    )
    rows = []
    for group in groups:
        student = students[group["student_id"]]
        guardian = guardians.get(student.pk)
        rows.append(
            DefaulterRow(
                student=student,
                guardian=guardian,
                phone=student.guardian_phone or (guardian.phone if guardian else ""),
                unpaid_months=group["months"],
                total_due=group["due"],
                oldest_due=group["oldest"],
                blocked=student.pk in blocked,
            )
        )
    return sorted(rows, key=lambda row: (-row.total_due, row.oldest_due))


def defaulters_csv(rows: list[DefaulterRow]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "Student",
            "Student ID",
            "Guardian",
            "Phone",
            "Unpaid months",
            "Total due",
            "Oldest due date",
            "Portal blocked",
        ]
    )
    for row in rows:
        guardian = row.guardian
        writer.writerow(
            [
                csv_cell(str(row.student)),
                csv_cell(row.student.student_code),
                csv_cell(
                    (guardian.get_full_name() or guardian.email) if guardian else ""
                ),
                csv_cell(row.phone),
                row.unpaid_months,
                row.total_due,
                row.oldest_due.isoformat(),
                "Yes" if row.blocked else "No",
            ]
        )
    return out.getvalue()


# Challan dashboard (SPEC 8)


@dataclass(frozen=True)
class ChallanNumbers:
    month: date
    billed: Decimal
    collected: Decimal
    outstanding: Decimal
    by_status: list[tuple[str, int]]
    waiting_receipts: int
    defaulters: int


def challan_dashboard(user: Any, institute: Any, today: date) -> ChallanNumbers:
    from apps.finance.models import ReceiptStatus, ReceiptSubmission

    month = today.replace(day=1)
    this_month = Challan.objects.for_user(user).filter(month=month)
    live = this_month.exclude(status=ChallanStatus.CANCELLED)
    totals = live.aggregate(
        billed=Sum(F("amount") + F("late_fee")),
        owed=Sum(F("amount") + F("late_fee") - F("paid")),
    )
    collected = (
        Payment.objects.for_user(user)
        .filter(paid_on__gte=month, paid_on__lte=today)
        .aggregate(total=Sum("amount"))["total"]
    )
    counts = dict(this_month.values_list("status").annotate(n=Count("pk")))
    overdue = live.filter(
        status__in=[ChallanStatus.PENDING, ChallanStatus.PARTIAL], due_date__lt=today
    ).count()
    by_status = [
        (label, counts.get(value, 0)) for value, label in ChallanStatus.choices
    ]
    by_status.append(("Overdue", overdue))
    return ChallanNumbers(
        month=month,
        billed=totals["billed"] or ZERO,
        collected=collected or ZERO,
        outstanding=totals["owed"] or ZERO,
        by_status=by_status,
        waiting_receipts=ReceiptSubmission.objects.for_user(user)
        .filter(status=ReceiptStatus.WAITING)
        .count(),
        defaulters=len(defaulters(user, institute, today)),
    )
