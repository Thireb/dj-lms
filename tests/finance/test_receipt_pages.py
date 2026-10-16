"""Roadmap 7.3b part 2: guardian Fee pay (SPEC 3, 4.17), the admin Receipt
inbox (SPEC 3, 4.9), the private file views and the notifications."""

from __future__ import annotations

from datetime import timedelta

import pytest
from apps.core.tenancy import tenant_context
from apps.finance.models import ReceiptStatus, ReceiptSubmission
from apps.finance.services import generate_challans
from apps.notifications.models import Notification
from django.urls import reverse
from django.utils import timezone

from tests.finance.conftest import add_plan, give_plan, png_upload
from tests.lectures.conftest import signed_in

TODAY = timezone.localdate()
FEE_PAY = reverse("guardian:fee_pay")
INBOX = reverse("admin:receipt_inbox")


@pytest.fixture
def owing(fees_school):
    give_plan(fees_school.student_1, add_plan(fees_school, "Tuition", "1000"))
    institute = fees_school.morning.institute
    with tenant_context(institute):
        (challan,) = generate_challans(
            institute,
            TODAY.replace(day=1),
            TODAY + timedelta(days=3),
            [fees_school.student_1],
        )
    return challan


def _send(school, challan, amount="1000"):
    return signed_in(school.guardian_1.user).post(
        FEE_PAY,
        {
            "challans": [challan.pk],
            "amount": amount,
            "paid_on": TODAY.isoformat(),
            "reference": "TX-9",
            "file": png_upload(),
        },
    )


@pytest.mark.django_db
def test_fee_pay_form_and_history(fees_school, admin, owing) -> None:
    client = signed_in(fees_school.guardian_1.user)
    html = client.get(FEE_PAY).content.decode()
    assert (
        owing.number in html
        and 'value="1000' in html
        and "No receipts sent yet." in html
    )
    response = _send(fees_school, owing)
    assert response.status_code == 302
    receipt = ReceiptSubmission.unscoped.get()
    assert (receipt.status, receipt.submitted_by) == (
        ReceiptStatus.WAITING,
        fees_school.guardian_1.user,
    )
    html = client.get(FEE_PAY).content.decode()
    assert receipt.number in html and "Waiting" in html
    note = Notification.unscoped.get(user=admin)
    assert note.event == "receipt_submitted"
    assert note.link == reverse("admin:receipt_detail", kwargs={"pk": receipt.pk})


@pytest.mark.django_db
def test_files_are_private(fees_school, admin, owing) -> None:
    _send(fees_school, owing)
    receipt = ReceiptSubmission.unscoped.get()
    mine = reverse("guardian:receipt_file", kwargs={"pk": receipt.pk})
    response = signed_in(fees_school.guardian_1.user).get(mine)
    assert response["Content-Type"] == "image/png"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert "no-store" in response["Cache-Control"]
    assert b"".join(response.streaming_content).startswith(b"\x89PNG")
    assert signed_in(fees_school.guardian_2.user).get(mine).status_code == 404
    admin_url = reverse("admin:receipt_file", kwargs={"pk": receipt.pk})
    assert signed_in(admin).get(admin_url).status_code == 200
    assert signed_in(fees_school.teacher_1.user).get(admin_url).status_code == 403


@pytest.mark.django_db
def test_too_much_is_refused_on_the_page(fees_school, owing) -> None:
    html = _send(fees_school, owing, amount="1500").content.decode()
    assert "The amount is more than the balance of 1000.00." in html
    assert not ReceiptSubmission.unscoped.exists()


@pytest.mark.django_db
def test_nothing_to_pay(fees_school) -> None:
    html = signed_in(fees_school.guardian_1.user).get(FEE_PAY).content.decode()
    assert "Nothing to pay." in html


@pytest.mark.django_db
def test_inbox_approve_and_the_guardian_is_told(fees_school, admin, owing) -> None:
    _send(fees_school, owing)
    receipt = ReceiptSubmission.unscoped.get()
    client = signed_in(admin)
    html = client.get(INBOX).content.decode()
    assert str(fees_school.student_1) in html and "Rs 1,000" in html and "TX-9" in html
    assert "Waiting" in client.get(INBOX, {"status": "waiting"}).content.decode()
    assert (
        "No receipts match"
        in client.get(INBOX, {"status": "rejected"}).content.decode()
    )
    detail = reverse("admin:receipt_detail", kwargs={"pk": receipt.pk})
    html = client.get(detail).content.decode()
    assert reverse("admin:receipt_file", kwargs={"pk": receipt.pk}) in html
    assert "<img" in html and "Reject receipt" in html
    client.post(reverse("admin:receipt_approve", kwargs={"pk": receipt.pk}))
    receipt.refresh_from_db()
    owing.refresh_from_db()
    assert receipt.status == ReceiptStatus.APPROVED and owing.status == "paid"
    note = Notification.unscoped.filter(user=fees_school.guardian_1.user).latest("pk")
    assert note.text == f"Your receipt {receipt.number} of Rs 1,000 is approved."
    assert note.link == FEE_PAY


@pytest.mark.django_db
def test_reject_with_a_reason(fees_school, admin, owing) -> None:
    _send(fees_school, owing)
    receipt = ReceiptSubmission.unscoped.get()
    client = signed_in(admin)
    url = reverse("admin:receipt_reject", kwargs={"pk": receipt.pk})
    client.post(url, {"reason": ""})
    receipt.refresh_from_db()
    assert receipt.status == ReceiptStatus.WAITING
    client.post(url, {"reason": "The photo is blurred."})
    receipt.refresh_from_db()
    assert (receipt.status, receipt.reason) == (
        ReceiptStatus.REJECTED,
        "The photo is blurred.",
    )
    note = Notification.unscoped.filter(user=fees_school.guardian_1.user).latest("pk")
    assert note.text == (
        "Your receipt was rejected: The photo is blurred. You can upload a new one."
    )


@pytest.mark.django_db
def test_basic_plan_has_no_fee_pay(school) -> None:
    assert signed_in(school.guardian_1.user).get(FEE_PAY).status_code == 403
