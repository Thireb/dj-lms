"""Roadmap 7.3c part 2: Fee defaulters (SPEC 3, 6.1) and the Challan
dashboard (SPEC 8). Real numbers; grace days are 5 (the default).

Student 1 (Morning): 5,050 a month. September (due 10 Sep): 2,000 paid on
3 Oct, so 3,050 is owed. October (due 10 Oct): unpaid.
Student 2 (Evening): Bus 800. October (due 10 Oct): unpaid.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.finance.models import Challan
from apps.finance.reports import challan_dashboard, defaulters, defaulters_csv
from apps.finance.services import cancel_challan, generate_challans, record_payment
from apps.finance.views import ChallanDashboardPage, FeeDefaultersPage
from apps.people.models import PortalAccessRule
from django.test import RequestFactory
from django.urls import reverse

from tests.conftest import make_user
from tests.finance.conftest import add_plan, give_plan
from tests.lectures.conftest import signed_in

SEP, OCT = date(2026, 9, 1), date(2026, 10, 1)
TODAY = date(2026, 10, 20)
PAGE = reverse("admin:fee_defaulters")
DASHBOARD = reverse("admin:dashboard_challan")


@pytest.fixture
def owing(fees_school):
    school = fees_school
    give_plan(school.student_1, add_plan(school), "percent", "10")
    give_plan(school.student_1, add_plan(school, "Lab", "1000"))
    give_plan(school.student_2, add_plan(school, "Bus", "800"))
    institute = school.morning.institute
    with tenant_context(institute):
        (sep,) = generate_challans(
            institute, SEP, date(2026, 9, 10), [school.student_1], today=SEP
        )
        generate_challans(
            institute,
            OCT,
            date(2026, 10, 10),
            [school.student_1, school.student_2],
            today=OCT,
        )
        day = date(2026, 10, 3)
        record_payment(
            sep, amount=Decimal("2000"), paid_on=day, method="cash", today=day
        )
    return school


def _rows(admin, today=TODAY, **filters):
    with tenant_context(admin.institute):
        return defaulters(admin, admin.institute, today, **filters)


def _summary(rows):
    return [
        (row.student.pk, row.unpaid_months, row.total_due, row.oldest_due)
        for row in rows
    ]


@pytest.mark.django_db
def test_defaulters_with_real_numbers(owing, admin) -> None:
    rows = _rows(admin)
    assert _summary(rows) == [
        (owing.student_1.pk, 2, Decimal("8100.00"), date(2026, 9, 10)),
        (owing.student_2.pk, 1, Decimal("800.00"), date(2026, 10, 10)),
    ]
    assert rows[0].guardian == owing.guardian_1.user
    assert rows[0].phone == owing.student_1.guardian_phone
    assert not rows[0].blocked


@pytest.mark.django_db
@pytest.mark.parametrize(
    "today, students",
    [
        # Overdue longer than 5 grace days: due 10 Oct counts from 16 Oct.
        (date(2026, 10, 15), ["student_1"]),
        (date(2026, 10, 16), ["student_1", "student_2"]),
        (date(2026, 9, 15), []),
        (date(2026, 9, 16), ["student_1"]),
    ],
)
def test_grace_days(owing, admin, today, students) -> None:
    expected = [getattr(owing, name).pk for name in students]
    assert [row.student.pk for row in _rows(admin, today)] == expected


@pytest.mark.django_db
def test_september_alone_before_october_is_overdue(owing, admin) -> None:
    rows = _rows(admin, date(2026, 10, 15))
    assert _summary(rows) == [
        (owing.student_1.pk, 1, Decimal("3050.00"), date(2026, 9, 10))
    ]


@pytest.mark.django_db
def test_filters(owing, admin) -> None:
    by_batch = _rows(admin, batch_id=owing.evening.pk)
    assert [row.student.pk for row in by_batch] == [owing.student_2.pk]
    by_amount = _rows(admin, min_amount=Decimal("801"))
    assert [row.student.pk for row in by_amount] == [owing.student_1.pk]
    assert len(_rows(admin, min_amount=Decimal("800"))) == 2


@pytest.mark.django_db
def test_paid_and_cancelled_challans_are_left_out(owing, admin) -> None:
    institute = owing.morning.institute
    with tenant_context(institute):
        bus = Challan.objects.get(student=owing.student_2)
        cancel_challan(bus)
        october = Challan.objects.get(student=owing.student_1, month=OCT)
        record_payment(
            october, amount=Decimal("5050"), paid_on=TODAY, method="cash", today=TODAY
        )
    assert _summary(_rows(admin)) == [
        (owing.student_1.pk, 1, Decimal("3050.00"), date(2026, 9, 10))
    ]


@pytest.mark.django_db
def test_blocked_flag_and_csv(owing, admin) -> None:
    # unscoped: test set-up outside a tenant context.
    PortalAccessRule.unscoped.create(
        institute=admin.institute, student=owing.student_2, blocked=True
    )
    rows = _rows(admin)
    assert [row.blocked for row in rows] == [False, True]
    lines = defaulters_csv(rows).splitlines()
    assert lines[0].startswith("Student,Student ID,Guardian,Phone,Unpaid months")
    assert lines[1].endswith(",2,8100.00,2026-09-10,No")
    assert lines[2].endswith(",1,800.00,2026-10-10,Yes")


@pytest.mark.django_db
def test_defaulters_scope_to_the_institute(owing) -> None:
    other = make_user(
        email="admin-b@example.com",
        role=Role.INSTITUTE_ADMIN,
        institute=owing.teacher_b.institute,
    )
    assert _rows(other) == []


# Pages


@pytest.mark.django_db
def test_defaulters_page(owing, admin) -> None:
    client = signed_in(admin)
    html = client.get(PAGE).content.decode()
    assert owing.student_1.student_code in html and "Rs 8,100" in html
    assert "5 grace days" in html
    compose = f"{reverse('admin:message_compose')}?to={owing.guardian_1.user.pk}"
    assert compose in html
    action = reverse("admin:portal_access_action", kwargs={"pk": owing.student_1.pk})
    assert action in html and 'value="block"' in html
    response = client.get(PAGE, {"export": "csv", "batch": owing.evening.pk})
    assert response["Content-Type"] == "text/csv"
    assert owing.student_2.student_code in response.content.decode()
    assert owing.student_1.student_code not in response.content.decode()
    response = client.get(PAGE, {"export": "pdf"})
    assert response.content.startswith(b"%PDF")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value", ["abc", "-5", "0", "1e999999", "1000000000", "NaN", "-Infinity", "<b>"]
)
def test_bad_minimum_is_ignored(owing, admin, value) -> None:
    response = signed_in(admin).get(PAGE, {"min": value})
    assert response.status_code == 200
    assert owing.student_2.student_code in response.content.decode()


@pytest.mark.django_db
def test_block_from_the_page_comes_back(owing, admin) -> None:
    back = f"{PAGE}?batch={owing.evening.pk}"
    url = reverse("admin:portal_access_action", kwargs={"pk": owing.student_2.pk})
    response = signed_in(admin).post(url, {"action": "block", "next": back})
    assert response["Location"] == back
    # unscoped: test assertion outside a tenant context.
    assert PortalAccessRule.unscoped.get(student=owing.student_2).blocked


def _sub_admin_view(view, url, institute, menus):
    email = f"sub-{'-'.join(menus)}@example.com"
    sub = make_user(email=email, role=Role.SUB_ADMIN, institute=institute)
    sub.allowed_menus = menus
    request = RequestFactory().get(url)
    request.user, request.institute = sub, institute
    with tenant_context(institute):
        response = view.as_view()(request)
        if hasattr(response, "render"):
            response.render()
    return response


@pytest.mark.django_db
def test_sub_admin_actions_follow_the_menus(owing) -> None:
    institute = owing.morning.institute
    finance = _sub_admin_view(FeeDefaultersPage, PAGE, institute, ["finance"])
    html = finance.content.decode()
    assert finance.status_code == 200 and owing.student_1.student_code in html
    action = reverse("admin:portal_access_action", kwargs={"pk": owing.student_1.pk})
    assert action not in html
    assert reverse("admin:message_compose") not in html
    both = _sub_admin_view(
        FeeDefaultersPage, PAGE, institute, ["finance", "people", "messages"]
    )
    html = both.content.decode()
    assert reverse("admin:message_compose") in html
    assert action in html
    assert (
        _sub_admin_view(FeeDefaultersPage, PAGE, institute, ["people"]).status_code
        == 403
    )


@pytest.mark.django_db
def test_other_roles_get_403(owing) -> None:
    for user in (owing.teacher_1.user, owing.student_1.user, owing.guardian_1.user):
        client = signed_in(user)
        assert client.get(PAGE).status_code == 403
        assert client.get(DASHBOARD).status_code == 403


# Challan dashboard (SPEC 8)


@pytest.mark.django_db
def test_dashboard_numbers(owing, admin) -> None:
    with tenant_context(admin.institute):
        numbers = challan_dashboard(admin, admin.institute, TODAY)
    assert numbers.money.month == OCT
    assert numbers.money.billed == Decimal("5850.00")
    assert numbers.money.collected == Decimal("2000.00")  # the September payment
    assert numbers.money.outstanding == Decimal("5850.00")
    statuses = dict(numbers.by_status)
    assert statuses["Pending"] == 2 and statuses["Paid"] == 0
    assert statuses["Overdue"] == 2
    assert numbers.money.waiting_receipts == 0 and numbers.defaulters == 2


@pytest.mark.django_db
def test_dashboard_leaves_out_cancelled_and_later_payments(owing, admin) -> None:
    with tenant_context(admin.institute):
        cancel_challan(Challan.objects.get(student=owing.student_2))
        october = Challan.objects.get(student=owing.student_1, month=OCT)
        later = date(2026, 10, 25)
        record_payment(
            october, amount=Decimal("1000"), paid_on=later, method="cash", today=later
        )
        numbers = challan_dashboard(admin, admin.institute, TODAY)
    assert (numbers.money.billed, numbers.money.outstanding) == (
        Decimal("5050.00"),
        Decimal("4050.00"),
    )
    assert numbers.money.collected == Decimal("2000.00")
    assert dict(numbers.by_status)["Cancelled"] == 1


@pytest.mark.django_db
def test_dashboard_page(owing, admin) -> None:
    html = signed_in(admin).get(DASHBOARD).content.decode()
    assert "Challan dashboard" in html and "Receipts waiting" in html
    assert "Defaulters (all months)" in html
    assert reverse("admin:fee_defaulters") in html
    institute = owing.morning.institute
    dashboards = _sub_admin_view(
        ChallanDashboardPage, DASHBOARD, institute, ["dashboards"]
    )
    assert dashboards.status_code == 200
    assert reverse("admin:challan_list") not in dashboards.content.decode()
    assert (
        _sub_admin_view(
            ChallanDashboardPage, DASHBOARD, institute, ["finance"]
        ).status_code
        == 403
    )
