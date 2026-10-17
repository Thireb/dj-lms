"""Fee notifications (SPEC 7): challan generated (the student and the
guardians), due in 3 days and overdue (the guardians; overdue also tells
the finance admins), payment recorded (the guardians), receipt submitted
(admins with Finance access), receipt approved or rejected (the guardian).
A guardian's text starts with the child's name."""

from __future__ import annotations

from typing import Any

from django.urls import reverse

from apps.accounts.models import User
from apps.core.menus import FINANCE, user_has_menu
from apps.core.roles import Role
from apps.finance.ui import date_text, money, month_text
from apps.notifications.audience import send_to_students
from apps.notifications.services import notify

STUDENT_URL = "student:fee_details"
GUARDIAN_URL = "guardian:fee_list"


def finance_admins(institute: Any) -> list[Any]:
    """Institute admins, and sub-admins with the Finance menu."""
    users = User.objects.filter(
        institute=institute, role__in=[Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]
    )
    return [user for user in users if user_has_menu(user, FINANCE)]


def receipt_submitted(receipt: Any) -> None:
    institute = receipt.institute
    amount = money(receipt.amount, institute)
    auto = " It was approved automatically." if receipt.status == "approved" else ""
    text = f"New fee receipt {receipt.number} for {receipt.student}: {amount}.{auto}"
    url = reverse("admin:receipt_detail", kwargs={"pk": receipt.pk})
    notify(finance_admins(institute), "receipt_submitted", text, url)


def receipt_result(receipt: Any) -> None:
    """SPEC 11: "Your receipt was rejected: [reason]. You can upload a new
    one." """
    if receipt.submitted_by is None:
        return
    if receipt.status == "rejected":
        text = f"Your receipt was rejected: {receipt.reason} You can upload a new one."
    else:
        amount = money(receipt.amount, receipt.institute)
        text = f"Your receipt {receipt.number} of {amount} is approved."
    notify([receipt.submitted_by], "receipt_result", text, reverse("guardian:fee_pay"))


def _to_family(event: str, challan: Any, text: str, *, student: bool) -> None:
    send_to_students(
        event,
        [challan.student],
        text,
        student_url=reverse(STUDENT_URL),
        guardian_url=reverse(GUARDIAN_URL),
        to_students=student,
    )


def challan_generated(challan: Any) -> None:
    cash = money(challan.total, challan.institute)
    text = (
        f"Fee challan {challan.number} for {month_text(challan.month)}: {cash}, "
        f"due {date_text(challan.due_date)}."
    )
    _to_family("challan_generated", challan, text, student=True)


def challan_due(challan: Any) -> None:
    cash = money(challan.balance, challan.institute)
    text = (
        f"Fee challan {challan.number} is due on {date_text(challan.due_date)}: "
        f"{cash} to pay."
    )
    _to_family("challan_due", challan, text, student=False)


def challan_overdue(challan: Any, late_fee_added: bool) -> None:
    institute = challan.institute
    unpaid = money(challan.balance, institute)
    text = f"Fee challan {challan.number} is overdue: {unpaid} is unpaid."
    if late_fee_added:
        text += f" A late fee of {money(challan.late_fee, institute)} was added."
    _to_family("challan_overdue", challan, text, student=False)


def overdue_summary(institute: Any, count: int) -> None:
    """SPEC 7 "challan overdue" for the admin: one notice per run, not one
    per challan."""
    noun = "challan" if count == 1 else "challans"
    text = f"{count} fee {noun} became overdue today."
    url = f"{reverse('admin:challan_list')}?status=overdue"
    notify(finance_admins(institute), "challan_overdue", text, url)


def payment_recorded(payment: Any) -> None:
    challan, institute = payment.challan, payment.institute
    left = challan.balance
    rest = (
        "The challan is paid in full."
        if left <= 0
        else f"{money(left, institute)} is left to pay."
    )
    text = (
        f"Payment {payment.number} of {money(payment.amount, institute)} for "
        f"challan {challan.number} is recorded. {rest}"
    )
    _to_family("payment_recorded", challan, text, student=False)
