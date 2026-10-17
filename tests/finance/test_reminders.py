"""Roadmap 7.4: fee notifications (SPEC 7) and the late fee (owner decision
2026-10-16: added once to a challan not paid in full by its due date).
Real numbers.

Student 1: 5,050 a month (Tuition 4,500 less 10%, Lab 1,000). October
challan, due Sat 10 Oct 2026. The late fee setting is 250.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.finance.models import Challan, ChallanStatus
from apps.finance.reminders import remind_challans
from apps.finance.services import generate_challans, record_payment
from apps.finance.tasks import remind_all_challans
from apps.notifications.models import Notification
from django.urls import reverse

from tests.conftest import make_user
from tests.finance.conftest import add_plan, give_plan

OCT = date(2026, 10, 1)
DUE = date(2026, 10, 10)


def _notes(user, event):
    # unscoped: test assertion outside a tenant context.
    return list(Notification.unscoped.filter(user=user, event=event).order_by("pk"))


@pytest.fixture
def billed(fees_school, admin):
    school = fees_school
    give_plan(school.student_1, add_plan(school), "percent", "10")
    give_plan(school.student_1, add_plan(school, "Lab", "1000"))
    institute = school.morning.institute
    settings = institute.settings
    settings.late_fee = Decimal("250")
    settings.save()
    with tenant_context(institute):
        (school.challan,) = generate_challans(
            institute, OCT, DUE, [school.student_1], today=OCT
        )
    return school


def _remind(school, today):
    institute = school.morning.institute
    with tenant_context(institute):
        run = remind_challans(institute, today)
    school.challan.refresh_from_db()
    return run


# Challan generated, payment recorded


@pytest.mark.django_db
def test_generated_goes_to_the_student_and_the_guardian(billed) -> None:
    (student,) = _notes(billed.student_1.user, "challan_generated")
    number = billed.challan.number
    assert student.text == (
        f"Fee challan {number} for Oct 2026: Rs 5,050, due Sat 10 Oct 2026."
    )
    assert student.link == reverse("student:fee_details")
    (guardian,) = _notes(billed.guardian_1.user, "challan_generated")
    assert guardian.text.startswith(f"For {billed.student_1}: Fee challan {number}")
    assert guardian.link == reverse("guardian:fee_list")
    assert _notes(billed.guardian_2.user, "challan_generated") == []


@pytest.mark.django_db
def test_payment_recorded_goes_to_the_guardian(billed) -> None:
    with tenant_context(billed.morning.institute):
        first = record_payment(
            billed.challan,
            amount=Decimal("2000"),
            paid_on=OCT,
            method="cash",
            today=OCT,
        )
        second = record_payment(
            billed.challan,
            amount=Decimal("3050"),
            paid_on=OCT,
            method="cash",
            today=OCT,
        )
    one, two = _notes(billed.guardian_1.user, "payment_recorded")
    assert one.text.endswith(
        f"Payment {first.number} of Rs 2,000 for challan {billed.challan.number} "
        "is recorded. Rs 3,050 is left to pay."
    )
    assert two.text.endswith(
        f"Payment {second.number} of Rs 3,050 for challan {billed.challan.number} "
        "is recorded. The challan is paid in full."
    )
    assert _notes(billed.student_1.user, "payment_recorded") == []


@pytest.mark.django_db
def test_an_approved_receipt_does_not_also_send_payment_recorded(billed) -> None:
    from apps.finance.receipts import approve_receipt, submit_receipt

    from tests.finance.conftest import png_upload

    with tenant_context(billed.morning.institute):
        receipt = submit_receipt(
            billed.guardian_1.user,
            billed.student_1,
            challans=[billed.challan],
            amount=Decimal("1000"),
            paid_on=OCT,
            reference="",
            upload=png_upload(),
        )
        approve_receipt(receipt, by=None)
    assert _notes(billed.guardian_1.user, "payment_recorded") == []
    assert len(_notes(billed.guardian_1.user, "receipt_result")) == 1


# Due in 3 days


@pytest.mark.django_db
def test_due_in_3_days_goes_once_to_the_guardian(billed) -> None:
    assert _remind(billed, date(2026, 10, 6)).due_soon == 0  # 4 days before
    assert _remind(billed, date(2026, 10, 7)).due_soon == 1
    assert billed.challan.due_reminded_on == date(2026, 10, 7)
    assert _remind(billed, date(2026, 10, 8)).due_soon == 0
    (note,) = _notes(billed.guardian_1.user, "challan_due")
    assert note.text.endswith(
        f"Fee challan {billed.challan.number} is due on Sat 10 Oct 2026: "
        "Rs 5,050 to pay."
    )
    assert _notes(billed.student_1.user, "challan_due") == []


@pytest.mark.django_db
def test_a_paid_challan_gets_no_reminders(billed) -> None:
    with tenant_context(billed.morning.institute):
        record_payment(
            billed.challan,
            amount=Decimal("5050"),
            paid_on=OCT,
            method="cash",
            today=OCT,
        )
    run = _remind(billed, date(2026, 10, 7))
    assert (run.due_soon, _remind(billed, date(2026, 10, 20)).overdue) == (0, 0)
    assert billed.challan.late_fee == 0


# Overdue and the late fee


@pytest.mark.django_db
def test_overdue_adds_the_late_fee_once(billed, admin) -> None:
    with tenant_context(billed.morning.institute):
        record_payment(
            billed.challan,
            amount=Decimal("2000"),
            paid_on=OCT,
            method="cash",
            today=OCT,
        )
    run = _remind(billed, DUE)
    assert (run.due_soon, run.overdue) == (0, 0)  # due today: neither
    assert _remind(billed, date(2026, 10, 11)).overdue == 1
    challan = billed.challan
    assert (challan.late_fee, challan.total, challan.balance) == (
        Decimal("250.00"),
        Decimal("5300.00"),
        Decimal("3300.00"),
    )
    assert challan.status == ChallanStatus.PARTIAL
    assert challan.overdue_on == date(2026, 10, 11)
    assert _remind(billed, date(2026, 10, 12)).overdue == 0
    billed.challan.refresh_from_db()
    assert billed.challan.late_fee == Decimal("250.00")
    (note,) = _notes(billed.guardian_1.user, "challan_overdue")
    assert note.text.endswith(
        f"Fee challan {challan.number} is overdue: Rs 3,300 is unpaid. "
        "A late fee of Rs 250 was added."
    )
    (summary,) = _notes(admin, "challan_overdue")
    assert summary.text == "1 fee challan became overdue today."
    assert summary.link == f"{reverse('admin:challan_list')}?status=overdue"


@pytest.mark.django_db
def test_no_late_fee_when_the_setting_is_0(billed) -> None:
    settings = billed.morning.institute.settings
    settings.late_fee = Decimal("0")
    settings.save()
    assert _remind(billed, date(2026, 10, 20)).overdue == 1
    assert billed.challan.late_fee == 0
    assert billed.challan.status == ChallanStatus.PENDING
    (note,) = _notes(billed.guardian_1.user, "challan_overdue")
    assert note.text.endswith("is overdue: Rs 5,050 is unpaid.")
    # A later late fee setting is not added to a challan already overdue.
    settings.late_fee = Decimal("250")
    settings.save()
    assert _remind(billed, date(2026, 10, 21)).overdue == 0
    assert billed.challan.late_fee == 0


@pytest.mark.django_db
def test_overdue_summary_goes_to_finance_admins_only(billed, admin) -> None:
    """A sub-admin's menus come with backlog S15; until then a sub-admin
    loaded by the job has none, so only the institute admin is told."""
    institute = billed.morning.institute
    sub = make_user(email="sub@example.com", role=Role.SUB_ADMIN, institute=institute)
    _remind(billed, date(2026, 10, 11))
    assert len(_notes(admin, "challan_overdue")) == 1
    assert _notes(sub, "challan_overdue") == []
    assert _notes(billed.teacher_1.user, "challan_overdue") == []


@pytest.mark.django_db
def test_the_hourly_task_uses_the_institute_date(billed) -> None:
    """The October challan is long past due by the real date of any run."""
    assert remind_all_challans() == 1
    challan = Challan.unscoped.get(pk=billed.challan.pk)
    assert challan.overdue_on is not None and challan.late_fee == Decimal("250.00")
    assert remind_all_challans() == 0
