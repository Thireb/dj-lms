"""Demo fees for seed_demo (Phase 7, SPEC 10): 3 fee plans, 3 months of
challans (paid, partial, pending and overdue), 3 waiting receipts and 4
defaulters. Fake data only. A second run adds nothing.

The two older months are paid in full except by the 4 defaulters
(students 2, 6, 9 and 13), so exactly 4 students are overdue beyond the
grace days. This month is due a week from today: some paid, some partly
paid, the rest pending. The late fee is 200, added to the overdue challans
by the reminder run."""

from __future__ import annotations

import io
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import User
from apps.core.tenancy import tenant_context
from apps.core.timezone_utils import institute_today
from apps.finance.models import (
    Challan,
    ChallanLine,
    FeePlan,
    Payment,
    ReceiptSubmission,
    StudentFeePlan,
)
from apps.finance.receipts import submit_receipt
from apps.finance.reminders import remind_challans
from apps.finance.services import generate_challans, month_start, record_payment
from apps.institutes.models import Institute
from apps.people.demo import ACTIVE_STUDENTS, guardian_email, guardian_number
from apps.people.demo import student_email as email_of
from apps.people.models import ProfileStatus, StudentProfile

PLANS = (("Tuition", "4500"), ("Lab", "1000"), ("Transport", "1500"))
LATE_FEE = Decimal("200")
DEFAULTERS = {2, 6, 9, 13}
# Old month unpaid or partly paid by each defaulter: (months back, part paid).
DEFAULTER_DEBTS = {
    2: [(2, "0"), (1, "0")],
    6: [(2, "2000"), (1, "0")],
    9: [(1, "1500")],
    13: [(2, "0")],
}
RECEIPT_STUDENTS = (1, 8, 11)
DEMO_ADMIN_EMAIL = "demo-admin@example.com"


def seed_fees(institute: Institute) -> None:
    with tenant_context(institute):
        if FeePlan.objects.exists():
            return
        settings = institute.settings
        settings.late_fee = LATE_FEE
        settings.save()
        today = institute_today(institute)
        students = _students()
        _give_plans(institute, students)
        admin = User.objects.filter(email=DEMO_ADMIN_EMAIL).first()
        this = month_start(today)
        for back in (2, 1):
            month = _months_back(this, back)
            challans = generate_challans(
                institute,
                month,
                month.replace(day=10),
                list(students.values()),
                today=month,
            )
            for challan in challans:
                _pay_old(challan, _number(students, challan), back, admin, today)
        current = generate_challans(
            institute,
            this,
            today + timedelta(days=7),
            list(students.values()),
            today=this,
        )
        for challan in current:
            _pay_current(challan, _number(students, challan), admin, today)
        _send_receipts(students, today)
        remind_challans(institute, today)


def _students() -> dict[int, StudentProfile]:
    profiles = StudentProfile.objects.filter(status=ProfileStatus.ACTIVE)
    by_email = {p.user.email: p for p in profiles.select_related("user")}
    numbers = range(1, ACTIVE_STUDENTS + 1)
    return {n: by_email[email_of(n)] for n in numbers if email_of(n) in by_email}


def _give_plans(institute: Institute, students: dict[int, StudentProfile]) -> None:
    plans = {
        name: FeePlan.objects.create(
            institute=institute, name=name, amount=Decimal(amount)
        )
        for name, amount in PLANS
    }
    for number, student in students.items():
        rows = [(plans["Tuition"], *_tuition_discount(number))]
        if number % 3 == 0:
            rows.append((plans["Lab"], "none", Decimal("0")))
        if number % 4 == 0:
            rows.append((plans["Transport"], "none", Decimal("0")))
        StudentFeePlan.objects.bulk_create(
            StudentFeePlan(
                institute=institute,
                student=student,
                fee_plan=plan,
                discount_type=kind,
                discount=value,
            )
            for plan, kind, value in rows
        )


def _tuition_discount(number: int) -> tuple[str, Decimal]:
    if number == 3:
        return "percent", Decimal("10")
    if number == 7:
        return "amount", Decimal("500")
    return "none", Decimal("0")


def _months_back(this: date, back: int) -> date:
    month = this
    for _ in range(back):
        month = month_start(month - timedelta(days=1))
    return month


def _number(students: dict[int, StudentProfile], challan: Challan) -> int:
    return next(n for n, s in students.items() if s.pk == challan.student_id)


def _pay(challan: Challan, amount: Decimal, day: date, admin: Any, today: date):
    if amount > 0:
        method = "cash" if challan.pk % 2 else "bank_transfer"
        record_payment(
            challan, amount=amount, paid_on=day, method=method, by=admin, today=today
        )


def _pay_old(challan, number, back, admin, today) -> None:
    debts = dict(DEFAULTER_DEBTS.get(number, []))
    part = debts.get(back)
    amount = challan.balance if part is None else Decimal(part)
    _pay(challan, amount, challan.month + timedelta(days=number % 9), admin, today)


def _pay_current(challan, number, admin, today) -> None:
    if number in DEFAULTERS or number % 3 == 2:
        return  # pending
    amount = challan.balance if number % 3 == 0 else Decimal("2000")
    day = min(today, challan.month + timedelta(days=number % 5))
    _pay(challan, amount, day, admin, today)


def _png(name: str) -> SimpleUploadedFile:
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (64, 40), "white").save(out, format="PNG")
    return SimpleUploadedFile(name, out.getvalue(), content_type="image/png")


def _send_receipts(students: dict[int, StudentProfile], today: date) -> None:
    for number in RECEIPT_STUDENTS:
        student = students.get(number)
        guardian = User.objects.filter(
            email=guardian_email(guardian_number(number))
        ).first()
        if student is None or guardian is None:
            continue
        challan = Challan.objects.get(student=student, month=month_start(today))
        submit_receipt(
            guardian,
            student,
            challans=[challan],
            amount=challan.balance,
            paid_on=today,
            reference=f"DEMO-{number:03d}",
            upload=_png(f"receipt-{number}.png"),
        )


def reset_fees(institute: Institute) -> int:
    """Delete the institute's fee rows and receipt files, before the people.
    Uses ``unscoped`` on purpose: a management command, one institute."""
    deleted = 0
    # unscoped: seed_demo --reset, limited to the demo institute.
    deleted += Payment.unscoped.filter(institute=institute).delete()[0]
    for receipt in ReceiptSubmission.unscoped.filter(institute=institute):
        receipt.file.delete(save=False)
    for model in (ReceiptSubmission, ChallanLine, Challan, StudentFeePlan, FeePlan):
        # unscoped: seed_demo --reset, limited to the demo institute.
        deleted += model.unscoped.filter(institute=institute).delete()[0]
    return deleted
