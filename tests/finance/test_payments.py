"""Roadmap 7.3: Process payment (SPEC 4.8), challan status (SPEC 6.1), the
receipt (SPEC 9.3) and the fee history. Real numbers."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.core.tenancy import tenant_context
from apps.finance.models import Challan, ChallanStatus, Payment
from apps.finance.pdf import receipt_pdf
from apps.finance.services import (
    NOT_OPEN,
    cancel_challan,
    fee_history,
    generate_challans,
    open_challans,
    record_payment,
)
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from tests.finance.conftest import add_plan, give_plan
from tests.lectures.conftest import signed_in

TODAY = timezone.localdate()


@pytest.fixture
def challan(fees_school):
    """Student 1: Tuition 4,500 less 10% and Lab 1,000 = 5,050."""
    give_plan(fees_school.student_1, add_plan(fees_school), "percent", "10")
    give_plan(fees_school.student_1, add_plan(fees_school, "Lab", "1000"))
    institute = fees_school.morning.institute
    with tenant_context(institute):
        (row,) = generate_challans(
            institute,
            TODAY.replace(day=1),
            TODAY + timedelta(days=5),
            [fees_school.student_1],
        )
    return row


def _pay(challan, amount, **kwargs):
    values = {"paid_on": TODAY, "method": "cash"}
    values.update(kwargs)
    with tenant_context(challan.institute):
        return record_payment(challan, amount=Decimal(amount), **values)


# Rules


@pytest.mark.django_db
def test_partial_then_full_payment(challan) -> None:
    first = _pay(challan, "2000")
    challan.refresh_from_db()
    assert (challan.paid, challan.balance, challan.status) == (
        Decimal("2000.00"),
        Decimal("3050.00"),
        ChallanStatus.PARTIAL,
    )
    second = _pay(challan, "3050", method="bank_transfer", reference="TX-77")
    challan.refresh_from_db()
    assert (challan.balance, challan.status) == (Decimal("0.00"), ChallanStatus.PAID)
    month = f"{TODAY:%Y%m}"
    assert (first.number, second.number) == (f"PAY-{month}-0001", f"PAY-{month}-0002")
    assert second.reference == "TX-77" and second.student_id == challan.student_id


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("amount", "values", "field", "error"),
    [
        ("5050.01", {}, "amount", "The amount is more than the balance of 5050.00."),
        ("0", {}, "amount", "The amount must be more than 0."),
        (
            "10",
            {"paid_on": TODAY + timedelta(days=1)},
            "paid_on",
            "The date cannot be in the future.",
        ),
        ("10", {"method": "barter"}, "method", "Choose how it was paid."),
    ],
)
def test_payment_rules(challan, amount, values, field, error) -> None:
    with pytest.raises(ValidationError) as caught:
        _pay(challan, amount, **values)
    assert caught.value.message_dict == {field: [error]}
    assert not Payment.unscoped.exists()


@pytest.mark.django_db
def test_a_cancelled_challan_takes_no_payment(challan) -> None:
    with tenant_context(challan.institute):
        cancel_challan(challan)
    with pytest.raises(ValidationError, match=NOT_OPEN):
        _pay(challan, "10")


@pytest.mark.django_db
def test_the_late_fee_counts_in_the_balance(challan) -> None:
    Challan.unscoped.filter(pk=challan.pk).update(late_fee=Decimal("250"))
    challan.refresh_from_db()
    _pay(challan, "5050")
    challan.refresh_from_db()
    assert (challan.balance, challan.status) == (
        Decimal("250.00"),
        ChallanStatus.PARTIAL,
    )
    _pay(challan, "250")
    challan.refresh_from_db()
    assert challan.status == ChallanStatus.PAID


@pytest.mark.django_db
def test_open_challans_and_history(fees_school, admin, challan) -> None:
    with tenant_context(admin.institute):
        assert list(open_challans(admin, challan.number)) == [challan]
    _pay(challan, "5050")
    with tenant_context(admin.institute):
        assert list(open_challans(admin, challan.number)) == []
        history = fee_history(fees_school.student_1)
    assert (history.billed, history.paid, history.due) == (
        Decimal("5050.00"),
        Decimal("5050.00"),
        Decimal("0.00"),
    )
    assert len(history.payments) == 1


@pytest.mark.django_db
def test_scopes(fees_school, admin, challan) -> None:
    _pay(challan, "100")
    with tenant_context(admin.institute):
        for user, seen in (
            (admin, 1),
            (fees_school.student_1.user, 1),
            (fees_school.guardian_1.user, 1),
            (fees_school.student_2.user, 0),
            (fees_school.guardian_2.user, 0),
            (fees_school.teacher_1.user, 0),
        ):
            assert Payment.objects.for_user(user).count() == seen, user


# Pages


@pytest.mark.django_db
def test_process_payment_pages(fees_school, admin, challan) -> None:
    client = signed_in(admin)
    process = reverse("admin:payment_process")
    assert "Search to start." in client.get(process).content.decode()
    html = client.get(
        process, {"q": fees_school.student_1.student_code}
    ).content.decode()
    pay = reverse("admin:challan_pay", kwargs={"pk": challan.pk})
    assert challan.number in html and f'href="{pay}"' in html
    html = client.get(pay).content.decode()
    assert 'value="5050' in html and "balance Rs 5,050" in html
    response = client.post(
        pay, {"amount": "2000", "paid_on": TODAY.isoformat(), "method": "cash"}
    )
    assert response["Location"] == reverse(
        "admin:challan_detail", kwargs={"pk": challan.pk}
    )
    html = client.get(response["Location"]).content.decode()
    assert "PAY-" in html and "Rs 2,000" in html and "Partial" in html
    html = client.post(
        pay, {"amount": "9999", "paid_on": TODAY.isoformat(), "method": "cash"}
    ).content.decode()
    assert "The amount is more than the balance of 3050.00." in html


@pytest.mark.django_db
def test_receipt_pdf_and_balance_after(fees_school, admin, challan) -> None:
    first = _pay(challan, "2000")
    _pay(challan, "1000")
    with tenant_context(admin.institute):
        content = receipt_pdf(Payment.unscoped.get(pk=first.pk), admin.institute)
    assert content.startswith(b"%PDF")
    url = reverse("admin:payment_receipt", kwargs={"pk": first.pk})
    response = signed_in(admin).get(url)
    assert response["Content-Type"] == "application/pdf"
    assert f'filename="{first.number}.pdf"' in response["Content-Disposition"]


@pytest.mark.django_db
def test_receipt_shows_the_balance_after(fees_school, admin, challan) -> None:
    from apps.finance.pdf import receipt_context

    first = _pay(challan, "2000")
    _pay(challan, "1000")
    with tenant_context(admin.institute):
        context = receipt_context(Payment.unscoped.get(pk=first.pk), admin.institute)
    assert context["balance_after"] == "Rs 3,050"  # after the first payment only
    assert context["words"] == "Two thousand rupees only"


@pytest.mark.django_db
def test_fee_history_page(fees_school, admin, challan) -> None:
    _pay(challan, "2000")
    url = reverse("admin:student_fee_history", kwargs={"pk": fees_school.student_1.pk})
    html = signed_in(admin).get(url).content.decode()
    assert challan.number in html and "Rs 3,050" in html and "PAY-" in html


@pytest.mark.django_db
def test_paid_challan_has_nothing_to_pay(fees_school, admin, challan) -> None:
    _pay(challan, "5050")
    pay = reverse("admin:challan_pay", kwargs={"pk": challan.pk})
    response = signed_in(admin).get(pay)
    assert response.status_code == 302
