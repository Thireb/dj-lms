"""Roadmap 7.3c part 1: daily, monthly and yearly fee reports (SPEC 3,
9.4). Real numbers.

Student 1 (Morning): 5,050 a month (Tuition 4,500 less 450, Lab 1,000).
Student 2 (Evening): Bus 800. September: student 1, paid in full on 20 Sep.
October: both; student 1 pays 2,000 on 5 Oct, student 2 pays 800 on 6 Oct.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from apps.core.tenancy import tenant_context
from apps.finance.reports import csv_cell, fee_report, report_csv
from apps.finance.services import generate_challans, record_payment
from django.urls import reverse

from tests.finance.conftest import add_plan, give_plan
from tests.lectures.conftest import signed_in

SEP, OCT = date(2026, 9, 1), date(2026, 10, 1)


@pytest.fixture
def ledger(fees_school):
    school = fees_school
    give_plan(school.student_1, add_plan(school), "percent", "10")
    give_plan(school.student_1, add_plan(school, "Lab", "1000"))
    give_plan(school.student_2, add_plan(school, "Bus", "800"))
    institute = school.morning.institute
    with tenant_context(institute):
        (sep,) = generate_challans(
            institute,
            SEP,
            date(2026, 9, 10),
            [school.student_1],
            today=date(2026, 9, 3),
        )
        oct_1, oct_2 = generate_challans(
            institute,
            OCT,
            date(2026, 10, 10),
            [school.student_1, school.student_2],
            today=date(2026, 10, 2),
        )
        for challan, amount, day in (
            (sep, "5050", date(2026, 9, 20)),
            (oct_1, "2000", date(2026, 10, 5)),
            (oct_2, "800", date(2026, 10, 6)),
        ):
            record_payment(
                challan, amount=Decimal(amount), paid_on=day, method="cash", today=day
            )
    return school


def _report(admin, kind, start=SEP, end=date(2026, 10, 31), **kwargs):
    with tenant_context(admin.institute):
        return fee_report(admin, kind, start, end, **kwargs)


def _numbers(row):
    return (row.challans, row.billed, row.collected, row.discounts, row.outstanding)


@pytest.mark.django_db
def test_monthly_report(ledger, admin) -> None:
    report = _report(admin, "monthly")
    assert [row.period for row in report.rows] == [OCT, SEP]
    october, september = report.rows
    D = Decimal
    assert _numbers(october) == (
        2,
        D("5850.00"),
        D("2800.00"),
        D("450.00"),
        D("3050.00"),
    )
    assert _numbers(september) == (
        1,
        D("5050.00"),
        D("5050.00"),
        D("450.00"),
        D("0.00"),
    )
    assert _numbers(report.totals) == (
        3,
        D("10900.00"),
        D("7850.00"),
        D("900.00"),
        D("3050.00"),
    )


@pytest.mark.django_db
def test_batch_filter(ledger, admin) -> None:
    october = _report(admin, "monthly", batch_id=ledger.morning.pk).rows[0]
    D = Decimal
    assert _numbers(october) == (
        1,
        D("5050.00"),
        D("2000.00"),
        D("450.00"),
        D("3050.00"),
    )


@pytest.mark.django_db
def test_daily_and_yearly_reports(ledger, admin) -> None:
    daily = {row.period: row for row in _report(admin, "daily", OCT).rows}
    assert set(daily) == {date(2026, 10, 2), date(2026, 10, 5), date(2026, 10, 6)}
    assert (daily[date(2026, 10, 2)].challans, daily[date(2026, 10, 2)].billed) == (
        2,
        Decimal("5850.00"),
    )
    assert daily[date(2026, 10, 5)].collected == Decimal("2000.00")
    (year,) = _report(admin, "yearly", date(2026, 1, 1), date(2026, 12, 31)).rows
    assert (year.period, year.challans, year.collected) == (
        date(2026, 1, 1),
        3,
        Decimal("7850.00"),
    )


@pytest.mark.django_db
def test_csv(ledger, admin) -> None:
    text = report_csv(_report(admin, "monthly"))
    lines = text.strip().splitlines()
    assert lines[0] == "Month,Challans,Billed,Collected,Discounts,Outstanding"
    assert lines[1] == "Oct 2026,2,5850.00,2800.00,450.00,3050.00"
    assert lines[-1] == "Total,3,10900.00,7850.00,900.00,3050.00"


@pytest.mark.parametrize(
    ("value", "safe"),
    [
        ("=SUM(A1)", "'=SUM(A1)"),
        ("+1", "'+1"),
        ("-1", "'-1"),
        ("@x", "'@x"),
        ("Ali", "Ali"),
    ],
)
def test_csv_cells_are_not_formulas(value, safe) -> None:
    assert csv_cell(value) == safe


@pytest.mark.django_db
def test_report_pages(ledger, admin) -> None:
    client = signed_in(admin)
    url = reverse("admin:fee_report_monthly")
    params = {"from": "2026-09-01", "to": "2026-10-31"}
    html = client.get(url, params).content.decode()
    assert "Oct 2026" in html and "Rs 5,850" in html and "Total" in html
    response = client.get(url, {**params, "export": "csv"})
    assert response["Content-Type"] == "text/csv"
    assert "attachment" in response["Content-Disposition"]
    assert b"Oct 2026,2,5850.00" in response.content
    response = client.get(url, {**params, "export": "pdf"})
    assert response[
        "Content-Type"
    ] == "application/pdf" and response.content.startswith(b"%PDF")
    for name in ("fee_report_daily", "fee_report_yearly"):
        assert client.get(reverse(f"admin:{name}")).status_code == 200


@pytest.mark.django_db
def test_reports_scope_to_the_institute(ledger) -> None:
    from apps.core.roles import Role

    from tests.conftest import make_user

    other = make_user(
        email="admin-b@example.com",
        role=Role.INSTITUTE_ADMIN,
        institute=ledger.teacher_b.institute,
    )
    assert _report(other, "monthly").rows == []


@pytest.mark.django_db
def test_cancelled_challans_are_left_out(ledger, admin) -> None:
    from apps.finance.services import cancel_challan

    institute = ledger.morning.institute
    nov = date(2026, 11, 1)
    with tenant_context(institute):
        (challan,) = generate_challans(
            institute, nov, date(2026, 11, 10), [ledger.student_2], today=nov
        )
        cancel_challan(challan)
    assert _report(admin, "monthly", nov, date(2026, 11, 30)).rows == []
