"""Roadmap 7.5: student Fee details, guardian Fee and challans with Print,
and the fee numbers on the dashboards (SPEC 3 and 8). Real numbers.

Student 1: 5,050 a month (Tuition 4,500 less 10%, Lab 1,000). Last month:
2,000 paid. This month: 1,010 paid. Student 2: Bus 800 this month, unpaid.
The academic year starts this month, so "this year" is this month only.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.finance.models import Challan
from apps.finance.reports import academic_year_start, fee_totals
from apps.finance.services import cancel_challan, generate_challans, record_payment
from apps.institutes.models import Plan
from django.urls import reverse
from django.utils import timezone

from tests.conftest import make_user
from tests.finance.conftest import add_plan, give_plan
from tests.lectures.conftest import signed_in

STUDENT_PAGE = reverse("student:fee_details")
GUARDIAN_PAGE = reverse("guardian:fee_list")


@pytest.fixture
def fees(fees_school):
    school = fees_school
    give_plan(school.student_1, add_plan(school), "percent", "10")
    give_plan(school.student_1, add_plan(school, "Lab", "1000"))
    give_plan(school.student_2, add_plan(school, "Bus", "800"))
    institute = school.morning.institute
    today = timezone.localdate()
    this = today.replace(day=1)
    last = (this - timedelta(days=1)).replace(day=1)
    settings = institute.settings
    settings.academic_year_start_month = this.month
    settings.save()
    with tenant_context(institute):
        (old,) = generate_challans(
            institute, last, last, [school.student_1], today=last
        )
        new, _ = generate_challans(
            institute, this, today, [school.student_1, school.student_2], today=this
        )
        for challan, amount in ((old, "2000"), (new, "1010")):
            record_payment(
                challan, amount=Decimal(amount), paid_on=today, method="cash"
            )
    school.old, school.new = old, new
    return school


@pytest.mark.django_db
def test_fee_totals_with_real_numbers(fees) -> None:
    with tenant_context(fees.morning.institute):
        every = fee_totals(fees.student_1)
        year = fee_totals(fees.student_1, since=fees.new.month)
        bus = fee_totals(fees.student_2)
    assert (every.billed, every.paid, every.due, every.pending) == (
        Decimal("10100.00"),
        Decimal("3010.00"),
        Decimal("7090.00"),
        2,
    )
    assert every.paid_percent == 29  # 29.8, rounded down
    assert (year.billed, year.paid, year.paid_percent) == (
        Decimal("5050.00"),
        Decimal("1010.00"),
        20,
    )
    assert (bus.due, bus.paid_percent) == (Decimal("800.00"), 0)


@pytest.mark.django_db
def test_cancelled_challans_and_no_challans(fees) -> None:
    with tenant_context(fees.morning.institute):
        cancel_challan(Challan.objects.get(student=fees.student_2))
        bus = fee_totals(fees.student_2)
        none = fee_totals(fees.student_new)
    assert (bus.billed, bus.due, bus.pending, bus.paid_percent) == (0, 0, 0, None)
    assert none.paid_percent is None


@pytest.mark.parametrize(
    "start, today, first",
    [
        (4, date(2026, 10, 16), date(2026, 4, 1)),
        (4, date(2026, 4, 1), date(2026, 4, 1)),
        (4, date(2026, 3, 31), date(2025, 4, 1)),
        (1, date(2026, 1, 5), date(2026, 1, 1)),
        (9, date(2026, 8, 31), date(2025, 9, 1)),
    ],
)
def test_academic_year_start(start, today, first) -> None:
    class Settings:
        academic_year_start_month = start

    class Institute:
        settings = Settings()

    assert academic_year_start(Institute(), today) == first


# Student Fee details


@pytest.mark.django_db
def test_student_fee_details(fees) -> None:
    html = signed_in(fees.student_1.user).get(STUDENT_PAGE).content.decode()
    for text in ("Total billed", "Rs 10,100", "Rs 3,010", "Rs 7,090"):
        assert text in html
    assert fees.old.number in html and fees.new.number in html
    assert html.index(fees.new.number) < html.index(fees.old.number)  # newest first
    bus = Challan.unscoped.get(student=fees.student_2)
    assert bus.number not in html
    assert "/pdf/" not in html  # Print is the guardian's


@pytest.mark.django_db
def test_student_does_not_see_cancelled_challans(fees) -> None:
    with tenant_context(fees.morning.institute):
        bus = Challan.objects.get(student=fees.student_2)
        cancel_challan(bus)
    html = signed_in(fees.student_2.user).get(STUDENT_PAGE).content.decode()
    assert bus.number not in html and "No challans yet." in html


# Guardian Fee and challans


@pytest.mark.django_db
def test_guardian_fee_list_and_print(fees) -> None:
    client = signed_in(fees.guardian_1.user)
    html = client.get(GUARDIAN_PAGE).content.decode()
    pdf = reverse("guardian:challan_pdf", kwargs={"pk": fees.new.pk})
    assert fees.new.number in html and pdf in html
    assert reverse("guardian:fee_pay") in html
    response = client.get(pdf)
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


@pytest.mark.django_db
def test_guardian_prints_only_their_children(fees) -> None:
    bus = Challan.unscoped.get(student=fees.student_2)
    url = reverse("guardian:challan_pdf", kwargs={"pk": bus.pk})
    assert signed_in(fees.guardian_1.user).get(url).status_code == 404
    assert signed_in(fees.guardian_2.user).get(url).status_code == 200
    with tenant_context(fees.morning.institute):
        cancel_challan(Challan.objects.get(pk=bus.pk))
    assert signed_in(fees.guardian_2.user).get(url).status_code == 404


@pytest.mark.django_db
def test_other_roles_get_403(fees, admin) -> None:
    pdf = reverse("guardian:challan_pdf", kwargs={"pk": fees.new.pk})
    for user in (admin, fees.teacher_1.user, fees.guardian_1.user):
        assert signed_in(user).get(STUDENT_PAGE).status_code == 403
    for user in (admin, fees.teacher_1.user, fees.student_1.user):
        client = signed_in(user)
        assert client.get(GUARDIAN_PAGE).status_code == 403
        assert client.get(pdf).status_code == 403


@pytest.mark.django_db
def test_without_the_fees_feature(school) -> None:
    institute = school.morning.institute
    institute.plan = Plan.objects.create(code="none", name="None", feature_keys=[])
    institute.save()
    assert signed_in(school.student_1.user).get(STUDENT_PAGE).status_code == 403
    assert signed_in(school.guardian_1.user).get(GUARDIAN_PAGE).status_code == 403
    html = signed_in(school.student_1.user).get(reverse("student:home")).content
    assert b"Fee paid this year" not in html
    html = signed_in(school.guardian_1.user).get(reverse("guardian:home")).content
    assert b"Nothing due" not in html


# Dashboards (SPEC 8)


@pytest.mark.django_db
def test_student_dashboard_fee_cards(fees) -> None:
    html = signed_in(fees.student_1.user).get(reverse("student:home")).content
    html = html.decode()
    assert "Fee paid this year" in html and "20%" in html
    assert "Rs 1,010 of Rs 5,050" in html
    assert "Rs 7,090" in html and "2 pending challans" in html


@pytest.mark.django_db
def test_guardian_dashboard_fees(fees) -> None:
    html = signed_in(fees.guardian_1.user).get(reverse("guardian:home")).content
    html = html.decode()
    assert "This year: billed Rs 5,050, paid Rs 1,010" in html
    assert "Rs 7,090 due" in html


@pytest.mark.django_db
def test_admin_fee_strip(fees, admin) -> None:
    html = signed_in(admin).get(reverse("admin:dashboard_main")).content.decode()
    month = f"{fees.new.month:%b %Y}"
    assert f"Billed in {month}" in html and "Rs 5,850" in html
    assert "Rs 3,010" in html  # both payments were made today
    assert "Rs 4,840" in html and "Receipts waiting" in html


@pytest.mark.django_db
def test_fee_strip_needs_the_finance_menu(fees) -> None:
    from apps.people.views import AdminDashboardPage
    from django.test import RequestFactory

    institute = fees.morning.institute
    sub = make_user(email="sub@example.com", role=Role.SUB_ADMIN, institute=institute)
    url = reverse("admin:dashboard_main")
    for menus, shown in ((["dashboards"], False), (["dashboards", "finance"], True)):
        sub.allowed_menus = menus
        request = RequestFactory().get(url)
        request.user, request.institute = sub, institute
        with tenant_context(institute):
            response = AdminDashboardPage.as_view()(request)
        assert ("Receipts waiting" in response.content.decode()) is shown
