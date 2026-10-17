"""Guardian fee receipts (roadmap 7.3b, SPEC 4.17, 4.9 and 6.1).

A guardian uploads proof of payment for one or more of a child's open
challans. The office approves it (payments are recorded, oldest challan
first) or rejects it with a reason. With "Auto-approve guardian receipts"
on, a receipt is approved as soon as it is sent.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.tenancy import require_tenant_context
from apps.core.timezone_utils import institute_today
from apps.finance import notices
from apps.finance.models import (
    Challan,
    ChallanStatus,
    PaymentMethod,
    ReceiptStatus,
    ReceiptSubmission,
)
from apps.finance.services import record_payment, to_money
from apps.people.models import GuardianStudentLink

MAX_FILE_BYTES = 5 * 1024 * 1024  # SPEC 4.17: up to 5 MB
IMAGE_FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
FILE_HELP = "Upload a JPG, PNG, WEBP or PDF file of up to 5 MB."
CHANGED = (
    "The chosen challans now owe {balance}, less than this receipt. Reject it "
    "with a reason, so the guardian can send a new one."
)


def check_receipt_file(upload: Any) -> None:
    """The type is checked from the content, not only the name: an image
    must open as that image, a PDF must start like one."""
    suffix = Path(getattr(upload, "name", "")).suffix.lower()
    if upload.size > MAX_FILE_BYTES:
        raise ValidationError({"file": "The file is larger than 5 MB."})
    if suffix == ".pdf":
        upload.seek(0)
        ok = upload.read(5) == b"%PDF-"
    elif suffix in IMAGE_FORMATS:
        from PIL import Image

        try:
            upload.seek(0)
            with Image.open(upload) as image:
                ok = image.format == IMAGE_FORMATS[suffix]
                image.verify()
        except Exception:
            ok = False
    else:
        ok = False
    upload.seek(0)
    if not ok:
        raise ValidationError({"file": FILE_HELP})


def open_challans_of(student: Any) -> list[Challan]:
    """The child's challans a receipt can pay, oldest first."""
    rows = Challan.objects.filter(
        student=student, status__in=[ChallanStatus.PENDING, ChallanStatus.PARTIAL]
    )
    return list(rows.order_by("month", "due_date", "pk"))


def submit_receipt(
    guardian: Any,
    student: Any,
    *,
    challans: list[Challan],
    amount: Decimal,
    paid_on: date,
    reference: str,
    upload: Any,
    today: date | None = None,
) -> ReceiptSubmission:
    """SPEC 4.17. Over-payment beyond the chosen balance is refused at
    submit (SPEC 6.1)."""
    # people.services imports the finance services, so import here.
    from apps.people.services import next_number

    require_tenant_context(student.institute)
    today = today or institute_today(student.institute)
    if not GuardianStudentLink.objects.filter(
        guardian__user=guardian, student=student
    ).exists():
        raise ValidationError("This student is not your child.")
    errors: dict[str, str] = {}
    open_ids = {challan.pk for challan in open_challans_of(student)}
    if not challans:
        errors["challans"] = "Choose at least one challan."
    elif any(challan.pk not in open_ids for challan in challans):
        errors["challans"] = "Choose open challans of this child."
    amount = to_money(amount)
    balance = sum((challan.balance for challan in challans), Decimal("0"))
    if amount <= 0:
        errors["amount"] = "The amount must be more than 0."
    elif challans and amount > balance:
        errors["amount"] = f"The amount is more than the balance of {balance}."
    if paid_on > today:
        errors["paid_on"] = "The date cannot be in the future."
    try:
        check_receipt_file(upload)
    except ValidationError as error:
        errors.update({key: value[0] for key, value in error.message_dict.items()})
    if errors:
        raise ValidationError(errors)
    with transaction.atomic():
        receipt = ReceiptSubmission(
            institute=student.institute,
            student=student,
            submitted_by=guardian,
            number=f"RCP-{next_number(student.institute, 'RCP'):04d}",
            amount=amount,
            paid_on=paid_on,
            reference=reference.strip()[:100],
        )
        receipt.file.save(
            f"receipt{Path(upload.name).suffix.lower()}", upload, save=False
        )
        receipt.save()
        receipt.challans.set(challans)
    if student.institute.settings.auto_approve_guardian_receipts:
        receipt = approve_receipt(receipt, by=None)
    notices.receipt_submitted(receipt)
    return receipt


def _locked_waiting(receipt: ReceiptSubmission) -> ReceiptSubmission:
    locked = ReceiptSubmission.objects.select_for_update().get(pk=receipt.pk)
    if locked.status != ReceiptStatus.WAITING:
        raise ValidationError(
            f"This receipt is already {locked.get_status_display().lower()}."
        )
    return locked


def approve_receipt(receipt: ReceiptSubmission, *, by: Any) -> ReceiptSubmission:
    """Record payments (method Online, the receipt's reference) against the
    chosen challans, oldest first (SPEC 6.1)."""
    require_tenant_context(receipt.institute)
    with transaction.atomic():
        locked = _locked_waiting(receipt)
        challans = list(
            Challan.objects.select_for_update()
            .filter(pk__in=locked.challans.values("pk"))
            .exclude(status__in=[ChallanStatus.CANCELLED, ChallanStatus.PAID])
            .order_by("month", "due_date", "pk")
        )
        balance = sum((challan.balance for challan in challans), Decimal("0"))
        if locked.amount > balance:
            raise ValidationError(CHANGED.format(balance=balance))
        left = locked.amount
        for challan in challans:
            if left <= 0:
                break
            part = min(left, challan.balance)
            record_payment(
                challan,
                amount=part,
                paid_on=locked.paid_on,
                method=PaymentMethod.ONLINE,
                reference=locked.reference or locked.number,
                by=by,
                today=max(locked.paid_on, institute_today(locked.institute)),
                receipt=locked,
            )
            left -= part
        locked.status = ReceiptStatus.APPROVED
        locked.reviewed_by = by
        locked.reviewed_at = timezone.now()
        locked.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        notices.receipt_result(locked)
    return locked


def reject_receipt(
    receipt: ReceiptSubmission, *, reason: str, by: Any
) -> ReceiptSubmission:
    """SPEC 4.9: a reason the guardian sees. Nothing changes on the
    challans (SPEC 6.1)."""
    require_tenant_context(receipt.institute)
    reason = reason.strip()
    if not reason:
        raise ValidationError({"reason": "Write the reason the guardian will see."})
    with transaction.atomic():
        locked = _locked_waiting(receipt)
        locked.status = ReceiptStatus.REJECTED
        locked.reason = reason[:200]
        locked.reviewed_by = by
        locked.reviewed_at = timezone.now()
        locked.save(update_fields=["status", "reason", "reviewed_by", "reviewed_at"])
        notices.receipt_result(locked)
    return locked
