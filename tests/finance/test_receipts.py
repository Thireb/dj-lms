"""Roadmap 7.3b part 1: guardian receipts (SPEC 4.17), approve (payments,
oldest challan first) and reject (SPEC 4.9, 6.1). Real numbers."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.core.tenancy import tenant_context
from apps.finance.models import ChallanStatus, Payment, ReceiptStatus, ReceiptSubmission
from apps.finance.receipts import (
    approve_receipt,
    check_receipt_file,
    reject_receipt,
    submit_receipt,
)
from apps.finance.services import generate_challans, record_payment
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from tests.finance.conftest import add_plan, give_plan, pdf_upload, png_upload

TODAY = timezone.localdate()


@pytest.fixture
def two_months(fees_school, admin):
    """Student 1 owes 1,000 for last month and 1,000 for this month."""
    give_plan(fees_school.student_1, add_plan(fees_school, "Tuition", "1000"))
    institute = fees_school.morning.institute
    month = TODAY.replace(day=1)
    earlier = (month - timedelta(days=1)).replace(day=1)
    with tenant_context(institute):
        older = generate_challans(institute, earlier, TODAY, [fees_school.student_1])
        newer = generate_challans(institute, month, TODAY, [fees_school.student_1])
    return older + newer


def _submit(school, challans, amount="1500", upload=None, guardian=None, **kwargs):
    values = {
        "challans": challans,
        "amount": Decimal(amount),
        "paid_on": TODAY,
        "reference": "TX-1",
        "upload": upload or png_upload(),
    }
    values.update(kwargs)
    with tenant_context(school.morning.institute):
        return submit_receipt(
            guardian or school.guardian_1.user, school.student_1, **values
        )


def _in(school, function, *args, **kwargs):
    with tenant_context(school.morning.institute):
        return function(*args, **kwargs)


# Files


@pytest.mark.parametrize(
    ("upload", "ok"),
    [
        (png_upload(), True),
        (pdf_upload(), True),
        (png_upload("receipt.jpg"), False),  # a PNG named .jpg
        (pdf_upload("receipt.pdf", b"<html>not a pdf"), False),
        (SimpleUploadedFile("receipt.exe", b"MZ"), False),
        (pdf_upload("big.pdf", b"%PDF-" + b"0" * (5 * 1024 * 1024)), False),
    ],
)
def test_file_check(upload, ok) -> None:
    if ok:
        check_receipt_file(upload)
    else:
        with pytest.raises(ValidationError):
            check_receipt_file(upload)


# Submit


@pytest.mark.django_db
def test_submit_saves_a_private_file(fees_school, two_months, private_media) -> None:
    receipt = _submit(fees_school, two_months)
    assert (receipt.number, receipt.status, receipt.amount) == (
        "RCP-0001",
        ReceiptStatus.WAITING,
        Decimal("1500.00"),
    )
    stored = private_media / receipt.file.name
    assert stored.exists() and receipt.file.name.startswith(
        f"receipts/{receipt.institute_id}/"
    )
    assert "receipt.png" not in receipt.file.name  # a random name on disk
    with tenant_context(receipt.institute):
        assert set(receipt.challans.all()) == set(two_months)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("values", "field", "error"),
    [
        (
            {"amount": "2000.01"},
            "amount",
            "The amount is more than the balance of 2000.00.",
        ),
        ({"challans": []}, "challans", "Choose at least one challan."),
        (
            {"paid_on": TODAY + timedelta(days=1)},
            "paid_on",
            "The date cannot be in the future.",
        ),
        (
            {"upload": pdf_upload(body=b"nope")},
            "file",
            "Upload a JPG, PNG, WEBP or PDF",
        ),
    ],
)
def test_submit_rules(fees_school, two_months, values, field, error) -> None:
    values.setdefault("challans", two_months)
    with pytest.raises(ValidationError) as caught:
        _submit(fees_school, **values)
    assert caught.value.message_dict[field][0].startswith(error)
    assert not ReceiptSubmission.unscoped.exists()


@pytest.mark.django_db
def test_only_the_childs_guardian_and_open_challans(fees_school, two_months) -> None:
    with pytest.raises(ValidationError, match="not your child"):
        _submit(fees_school, two_months, guardian=fees_school.guardian_2.user)
    _in(
        fees_school,
        record_payment,
        two_months[0],
        amount=Decimal("1000"),
        paid_on=TODAY,
        method="cash",
    )
    two_months[0].refresh_from_db()
    with pytest.raises(ValidationError) as caught:
        _submit(fees_school, two_months, amount="500")
    assert caught.value.message_dict == {
        "challans": ["Choose open challans of this child."]
    }


# Approve and reject


@pytest.mark.django_db
def test_approve_pays_the_oldest_challan_first(fees_school, admin, two_months) -> None:
    receipt = _submit(fees_school, two_months, amount="1500")
    approved = _in(fees_school, approve_receipt, receipt, by=admin)
    assert approved.status == ReceiptStatus.APPROVED and approved.reviewed_by == admin
    older, newer = two_months
    older.refresh_from_db()
    newer.refresh_from_db()
    assert (older.paid, older.status) == (Decimal("1000.00"), ChallanStatus.PAID)
    assert (newer.paid, newer.status) == (Decimal("500.00"), ChallanStatus.PARTIAL)
    payments = list(Payment.unscoped.order_by("pk"))
    assert [(p.amount, p.method, p.reference, p.receipt_id) for p in payments] == [
        (Decimal("1000.00"), "online", "TX-1", receipt.pk),
        (Decimal("500.00"), "online", "TX-1", receipt.pk),
    ]
    with pytest.raises(ValidationError, match="already approved"):
        _in(fees_school, approve_receipt, receipt, by=admin)


@pytest.mark.django_db
def test_approve_refuses_when_the_challans_owe_less_now(
    fees_school, admin, two_months
) -> None:
    receipt = _submit(fees_school, two_months, amount="1500")
    _in(
        fees_school,
        record_payment,
        two_months[0],
        amount=Decimal("1000"),
        paid_on=TODAY,
        method="cash",
    )
    with pytest.raises(
        ValidationError, match="now owe 1000.00, less than this receipt"
    ):
        _in(fees_school, approve_receipt, receipt, by=admin)
    receipt.refresh_from_db()
    assert receipt.status == ReceiptStatus.WAITING


@pytest.mark.django_db
def test_reject_needs_a_reason_and_changes_nothing(
    fees_school, admin, two_months
) -> None:
    receipt = _submit(fees_school, two_months)
    with pytest.raises(ValidationError):
        _in(fees_school, reject_receipt, receipt, reason="  ", by=admin)
    rejected = _in(
        fees_school, reject_receipt, receipt, reason="The amount is unclear.", by=admin
    )
    assert (rejected.status, rejected.reason) == (
        ReceiptStatus.REJECTED,
        "The amount is unclear.",
    )
    assert not Payment.unscoped.exists()


@pytest.mark.django_db
def test_auto_approve_setting(fees_school, two_months) -> None:
    settings = fees_school.morning.institute.settings
    settings.auto_approve_guardian_receipts = True
    settings.save()
    receipt = _submit(fees_school, two_months, amount="1000")
    assert receipt.status == ReceiptStatus.APPROVED and receipt.reviewed_by is None
    assert Payment.unscoped.count() == 1


@pytest.mark.django_db
def test_auto_approve_failure_leaves_the_receipt_waiting(
    fees_school, admin, two_months, monkeypatch, caplog
) -> None:
    """External re-audit item 3: the balance changes between the save and
    the approval (an office payment), so approve_receipt raises CHANGED.
    The receipt stays waiting, the office is told, the guardian sees no
    error."""
    import logging

    from apps.finance import receipts
    from apps.notifications.models import Notification

    settings = fees_school.morning.institute.settings
    settings.auto_approve_guardian_receipts = True
    settings.save()
    real_approve = receipts.approve_receipt

    def pay_first_then_approve(receipt, *, by):
        record_payment(
            two_months[0], amount=Decimal("1000"), paid_on=TODAY, method="cash"
        )
        return real_approve(receipt, by=by)

    monkeypatch.setattr(receipts, "approve_receipt", pay_first_then_approve)
    with caplog.at_level(logging.WARNING, logger="apps.finance.receipts"):
        receipt = _submit(fees_school, two_months, amount="1500")
    assert receipt.status == ReceiptStatus.WAITING
    assert ReceiptSubmission.unscoped.get().status == ReceiptStatus.WAITING
    assert Payment.unscoped.count() == 1  # the office payment only
    # unscoped: test assertion outside a tenant context.
    note = Notification.unscoped.get(user=admin, event="receipt_submitted")
    assert receipt.number in note.text and "approved automatically" not in note.text
    assert f"Receipt {receipt.pk}: auto-approve failed" in caplog.text


@pytest.mark.django_db
def test_scopes(fees_school, admin, two_months) -> None:
    _submit(fees_school, two_months)
    with tenant_context(admin.institute):
        for user, seen in (
            (admin, 1),
            (fees_school.guardian_1.user, 1),
            (fees_school.guardian_2.user, 0),
            (fees_school.teacher_1.user, 0),
        ):
            assert ReceiptSubmission.objects.for_user(user).count() == seen, user
