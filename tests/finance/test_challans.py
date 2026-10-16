"""Roadmap 7.2 part 1: challan generation (SPEC 4.7), records, cancel and
the overdue rule (SPEC 6.1). Real numbers."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.core.tenancy import tenant_context
from apps.finance.models import Challan, ChallanLine, ChallanStatus
from apps.finance.services import (
    CANCEL_PAID,
    NO_FEE,
    cancel_challan,
    generate_challans,
    is_overdue,
    list_challans,
    preview_challans,
)
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from tests.finance.conftest import add_plan, give_plan
from tests.lectures.conftest import signed_in

TODAY = date(2026, 10, 5)
OCT = date(2026, 10, 1)
DUE = date(2026, 10, 10)


def _in(school, function, *args, **kwargs):
    with tenant_context(school.morning.institute):
        return function(*args, **kwargs)


def _make(school, students, month=OCT, due=DUE, today=TODAY):
    institute = school.morning.institute
    return _in(school, generate_challans, institute, month, due, students, today=today)


@pytest.fixture
def billed(fees_school):
    """Student 1: Tuition 4,500 less 10% and Lab 1,000 = 5,050."""
    give_plan(fees_school.student_1, add_plan(fees_school), "percent", "10")
    give_plan(fees_school.student_1, add_plan(fees_school, "Lab", "1000"))
    return fees_school


# Generation


@pytest.mark.django_db
def test_preview_plans_and_skips(billed) -> None:
    students = [billed.student_1, billed.student_2]
    preview = _in(billed, preview_challans, OCT, students)
    assert [(p.student, p.amount) for p in preview.planned] == [
        (billed.student_1, Decimal("5050.00"))
    ]
    assert preview.skipped == [(billed.student_2, NO_FEE)]
    (challan,) = _make(billed, students)
    again = _in(billed, preview_challans, OCT, students)
    assert again.planned == [] and again.skipped[0] == (
        billed.student_1,
        f"Has {challan.number}",
    )


@pytest.mark.django_db
def test_generate_freezes_the_amount_and_lines(billed) -> None:
    (challan,) = _make(billed, [billed.student_1])
    assert (challan.number, challan.month, challan.issue_date, challan.due_date) == (
        "CH-202610-0001",
        OCT,
        TODAY,
        DUE,
    )
    assert (challan.amount, challan.paid, challan.status) == (
        Decimal("5050.00"),
        Decimal("0"),
        ChallanStatus.PENDING,
    )
    lines = ChallanLine.unscoped.filter(challan=challan)  # unscoped: assertion
    assert [(line.name, line.amount, line.discount) for line in lines] == [
        ("Lab", Decimal("1000.00"), Decimal("0.00")),
        ("Tuition", Decimal("4500.00"), Decimal("450.00")),
    ]
    # A later price change does not touch the challan (SPEC 6.1: frozen).
    from apps.finance.models import FeePlan

    FeePlan.unscoped.filter(name="Lab").update(amount=Decimal("2000"))
    challan.refresh_from_db()
    assert challan.amount == Decimal("5050.00")


@pytest.mark.django_db
def test_no_duplicates_and_cancelled_months_can_be_billed_again(billed) -> None:
    (first,) = _make(billed, [billed.student_1])
    assert _make(billed, [billed.student_1]) == []
    _in(billed, cancel_challan, first)
    (second,) = _make(billed, [billed.student_1])
    assert second.number == "CH-202610-0002"
    (november,) = _make(
        billed, [billed.student_1], month=date(2026, 11, 1), due=date(2026, 11, 10)
    )
    assert november.number == "CH-202611-0001"


@pytest.mark.django_db
def test_due_date_cannot_be_in_the_past(billed) -> None:
    with pytest.raises(ValidationError, match="Choose a due date today or later."):
        _make(billed, [billed.student_1], due=TODAY - timedelta(days=1))


@pytest.mark.django_db
def test_due_date_cannot_be_before_the_month(billed) -> None:
    with pytest.raises(ValidationError, match="cannot be before the month"):
        _make(
            billed, [billed.student_1], month=date(2026, 12, 1), due=date(2026, 11, 20)
        )


# Cancel and overdue (SPEC 6.1)


@pytest.mark.django_db
def test_a_challan_with_payments_cannot_be_cancelled(billed) -> None:
    (challan,) = _make(billed, [billed.student_1])
    Challan.unscoped.filter(pk=challan.pk).update(paid=Decimal("100"))
    with pytest.raises(ValidationError, match=CANCEL_PAID):
        _in(billed, cancel_challan, challan)


@pytest.mark.django_db
def test_overdue_after_the_due_date(billed) -> None:
    (challan,) = _make(billed, [billed.student_1])
    assert not is_overdue(challan, DUE)
    assert is_overdue(challan, DUE + timedelta(days=1))
    challan.status = ChallanStatus.PAID
    assert not is_overdue(challan, DUE + timedelta(days=1))


# Lists and scopes


@pytest.mark.django_db
def test_list_filters(billed, admin) -> None:
    (october,) = _make(billed, [billed.student_1])
    give_plan(billed.student_2, add_plan(billed, "Bus", "800"))
    (november,) = _make(
        billed, [billed.student_2], month=date(2026, 11, 1), due=date(2026, 11, 10)
    )

    def numbers(**filters):
        with tenant_context(admin.institute):
            return [
                c.number
                for c in list_challans(admin, today=date(2026, 10, 20), **filters)
            ]

    assert numbers() == [november.number, october.number]
    assert numbers(month=OCT) == [october.number]
    assert numbers(status="overdue") == [october.number]
    assert numbers(batch_id=billed.evening.pk) == [november.number]
    assert numbers(search=billed.student_2.student_code) == [november.number]


@pytest.mark.django_db
def test_scopes(billed, admin, anonymous_user) -> None:
    _make(billed, [billed.student_1])
    assert not Challan.objects.exists()
    assert not Challan.objects.for_user(anonymous_user).exists()
    with tenant_context(admin.institute):
        for user, seen in (
            (admin, 1),
            (billed.student_1.user, 1),
            (billed.guardian_1.user, 1),
            (billed.student_2.user, 0),
            (billed.guardian_2.user, 0),
            (billed.teacher_1.user, 0),
        ):
            assert Challan.objects.for_user(user).count() == seen, user


# Pages


@pytest.mark.django_db
def test_generate_preview_and_confirm(billed, admin) -> None:
    url = reverse("admin:challan_generate")
    client = signed_in(admin)
    assert client.get(url).status_code == 200
    month = timezone.localdate().replace(day=1)
    due = timezone.localdate() + timedelta(days=5)
    html = client.post(
        url, {"month": f"{month:%Y-%m}", "due_date": due.isoformat(), "scope": "all"}
    ).content.decode()
    assert "Preview: 1 challans" in html and "Rs 5,050" in html
    assert "Skipped: " in html and "No fee plan" in html
    response = client.post(
        url,
        {
            "month": month.isoformat(),
            "due_date": due.isoformat(),
            "students": [billed.student_1.pk, billed.student_2.pk],
        },
    )
    assert (
        response.status_code == 302 and f"month={month:%Y-%m}" in response["Location"]
    )
    assert Challan.unscoped.count() == 1  # student 2 has no plan: skipped again
    html = client.get(response["Location"]).content.decode()
    assert "CH-" in html and "Rs 5,050" in html


@pytest.mark.django_db
def test_detail_and_cancel(billed, admin) -> None:
    (challan,) = _make(
        billed,
        [billed.student_1],
        today=timezone.localdate(),
        due=timezone.localdate() + timedelta(days=3),
        month=timezone.localdate().replace(day=1),
    )
    client = signed_in(admin)
    detail = reverse("admin:challan_detail", kwargs={"pk": challan.pk})
    html = client.get(detail).content.decode()
    assert "Tuition" in html and "Rs 450" in html and "Cancel challan" in html
    client.post(reverse("admin:challan_cancel", kwargs={"pk": challan.pk}))
    challan.refresh_from_db()
    assert challan.status == ChallanStatus.CANCELLED


@pytest.mark.django_db
def test_other_institute_challan_is_404(billed, admin) -> None:
    (challan,) = _make(billed, [billed.student_1])
    Challan.unscoped.filter(pk=challan.pk).update(institute=billed.teacher_b.institute)
    detail = reverse("admin:challan_detail", kwargs={"pk": challan.pk})
    assert signed_in(admin).get(detail).status_code == 404
