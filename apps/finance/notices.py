"""Fee notifications (SPEC 7): receipt submitted (admins with Finance
access), receipt approved or rejected (the guardian)."""

from __future__ import annotations

from typing import Any

from django.urls import reverse

from apps.accounts.models import User
from apps.core.menus import FINANCE, user_has_menu
from apps.core.roles import Role
from apps.finance.ui import money
from apps.notifications.services import notify


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
