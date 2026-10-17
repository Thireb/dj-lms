"""Challan PDFs (roadmap 7.2, SPEC 9.1): HTML templates turned into PDF by
WeasyPrint (ARCHITECTURE 8). Three labelled copies on one A4 page;
several challans print one per page."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import F, Q, Sum
from django.template.loader import render_to_string

from apps.core.timezone_utils import institute_today
from apps.finance.models import Challan, ChallanStatus
from apps.finance.ui import date_text, money, month_text
from apps.finance.words import amount_in_words
from apps.people.models import GuardianStudentLink

COPIES = ("Institute copy", "Student copy", "Bank / office copy")
CURRENCY_WORDS = {  # (main unit, cents) for "amount in words"
    "PKR": ("rupees", "paisa"),
    "INR": ("rupees", "paisa"),
    "USD": ("dollars", "cents"),
    "GBP": ("pounds", "pence"),
    "AED": ("dirhams", "fils"),
    "SAR": ("riyals", "halalas"),
}
# SPEC 9.1 says the text is editable in settings; there is no such setting
# yet, so every institute prints this one (assumed).
PAYMENT_TEXT = (
    "Pay at the institute office or by bank transfer before the due date. "
    "Keep this copy as your proof of payment."
)


@dataclass(frozen=True)
class ChallanPrint:
    """Everything one challan prints, as text (amounts already formatted)."""

    challan: Challan
    month: str
    issued: str
    due: str
    student_line: str
    batches: str
    guardians: str
    lines: list[tuple[str, str, str, str]]  # fee, amount, discount, payable
    amount: str
    late_fee: str
    paid: str
    balance: str
    previous: str  # unpaid balance of older challans (information only)
    words: str


def _previous_balances(challans: list[Challan]) -> dict[int, Decimal]:
    """Each challan's previous balance: the unpaid total of the student's
    older challans that are not cancelled (one query per print)."""
    students = {challan.student_id for challan in challans}
    open_rows = (
        Challan.objects.filter(student_id__in=students)
        .exclude(status__in=[ChallanStatus.CANCELLED, ChallanStatus.PAID])
        .values("student_id", "month")
        .annotate(due=Sum(F("amount") + F("late_fee") - F("paid")))
    )
    result = {}
    for challan in challans:
        result[challan.pk] = sum(
            (
                row["due"]
                for row in open_rows
                if row["student_id"] == challan.student_id
                and row["month"] < challan.month
            ),
            Decimal("0"),
        )
    return result


def challan_prints(challans: list[Challan], institute: Any) -> list[ChallanPrint]:
    def cash(amount: Decimal) -> str:
        return money(amount, institute)

    unit, cents = CURRENCY_WORDS.get(
        institute.currency_code, (institute.currency_code, "cents")
    )
    previous = _previous_balances(challans)
    guardians: dict[int, list[str]] = {}
    links = GuardianStudentLink.objects.filter(
        student__in=[challan.student_id for challan in challans]
    ).select_related("guardian__user")
    for link in links:
        user = link.guardian.user
        phone = f", {user.phone}" if user.phone else ""
        guardians.setdefault(link.student_id, []).append(
            f"{user.get_full_name() or user.email}{phone}"
        )
    prints = []
    for challan in challans:
        student = challan.student
        batches = sorted(
            {row.batch.name for row in student.batch_subjects.select_related("batch")}
        )
        label = f", {student.class_label}" if student.class_label_id else ""
        prints.append(
            ChallanPrint(
                challan=challan,
                month=month_text(challan.month),
                issued=date_text(challan.issue_date),
                due=date_text(challan.due_date),
                student_line=f"{student} ({student.student_code}{label})",
                batches=", ".join(batches),
                guardians="; ".join(guardians.get(student.pk, [])) or "-",
                lines=[
                    (line.name, cash(line.amount), cash(line.discount), cash(line.net))
                    for line in challan.lines.all()
                ],
                amount=cash(challan.amount),
                late_fee=cash(challan.late_fee) if challan.late_fee else "",
                paid=cash(challan.paid) if challan.paid else "",
                balance=cash(challan.balance),
                previous=cash(previous[challan.pk]) if previous[challan.pk] else "",
                words=amount_in_words(challan.balance, unit, cents),
            )
        )
    return prints


def challan_html(challans: list[Challan], institute: Any) -> str:
    late_fee = institute.settings.late_fee
    return render_to_string(
        "finance/challan_pdf.html",
        {
            "institute": institute,
            "prints": challan_prints(challans, institute),
            "copies": COPIES,
            "payment_text": PAYMENT_TEXT,
            "late_fee": money(late_fee, institute) if late_fee else "",
            "printed": date_text(institute_today(institute)),
        },
    )


def challans_pdf(challans: list[Challan], institute: Any) -> bytes:
    from weasyprint import HTML

    return HTML(string=challan_html(challans, institute)).write_pdf()


# Payment receipt (SPEC 9.3)


def receipt_pdf(payment: Any, institute: Any) -> bytes:
    """Header, receipt no., date, student, challan no., amount, method,
    balance after, received by."""
    from weasyprint import HTML

    context = receipt_context(payment, institute)
    return HTML(
        string=render_to_string("finance/receipt_pdf.html", context)
    ).write_pdf()


def receipt_context(payment: Any, institute: Any) -> dict[str, Any]:
    """The receipt's text; "balance after" counts this payment and the ones
    before it."""
    challan = payment.challan
    earlier = challan.payments.filter(
        Q(paid_on__lt=payment.paid_on) | Q(paid_on=payment.paid_on, pk__lte=payment.pk)
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    by = payment.received_by
    unit, cents = CURRENCY_WORDS.get(
        institute.currency_code, (institute.currency_code, "cents")
    )
    return {
        "institute": institute,
        "payment": payment,
        "student": f"{payment.student} ({payment.student.student_code})",
        "date": date_text(payment.paid_on),
        "amount": money(payment.amount, institute),
        "words": amount_in_words(payment.amount, unit, cents),
        "balance_after": money(challan.total - earlier, institute),
        "received_by": (by.get_full_name() or by.email) if by else "-",
        "month": month_text(challan.month),
    }


# Report prints (SPEC 9.4: header, date range, table, totals row, page numbers)


def table_pdf(
    institute: Any,
    *,
    title: str,
    range_text: str,
    headings: list[str],
    rows: list[list[str]],
    has_total: bool,
    batch: str = "",
) -> bytes:
    from weasyprint import HTML

    html = render_to_string(
        "finance/report_pdf.html",
        {
            "institute": institute,
            "title": title,
            "range": range_text,
            "batch": batch,
            "headings": headings,
            "rows": rows,
            "has_total": has_total,
            "printed": date_text(institute_today(institute)),
        },
    )
    return HTML(string=html).write_pdf()
