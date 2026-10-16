"""Roadmap 7.1: fee plans (SPEC 4.4), a student's monthly fee with
discounts (SPEC 6.1), and the two new settings. Real numbers."""

from __future__ import annotations

from decimal import Decimal

import pytest
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.finance.models import FeePlan, StudentFeePlan
from apps.finance.services import (
    create_fee_plan,
    discount_amount,
    fee_lines,
    monthly_fee,
    update_fee_plan,
)
from apps.finance.ui import money
from apps.finance.views import FeePlanListPage
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.urls import reverse

from tests.conftest import make_user
from tests.finance.conftest import add_plan, give_plan
from tests.lectures.conftest import signed_in

LIST = reverse("admin:fee_plan_list")


def _in(school, function, *args, **kwargs):
    with tenant_context(school.morning.institute):
        return function(*args, **kwargs)


# Rules


@pytest.mark.django_db
def test_create_and_update_a_plan(fees_school) -> None:
    institute = fees_school.morning.institute
    plan = _in(
        fees_school,
        create_fee_plan,
        institute,
        name=" Tuition ",
        amount=Decimal("4500.005"),
    )
    assert (plan.name, plan.amount) == ("Tuition", Decimal("4500.01"))
    with pytest.raises(ValidationError) as error:
        _in(fees_school, create_fee_plan, institute, name="tuition", amount=Decimal(1))
    assert error.value.message_dict == {
        "name": ["A fee plan with this name already exists."]
    }
    with pytest.raises(ValidationError) as error:
        _in(fees_school, create_fee_plan, institute, name="Lab", amount=Decimal(0))
    assert "amount" in error.value.message_dict
    plan = _in(fees_school, update_fee_plan, plan, name="Tuition", amount=Decimal(5000))
    assert plan.amount == Decimal("5000.00")


@pytest.mark.parametrize(
    ("kind", "value", "off"),
    [
        ("none", "0", "0.00"),
        ("amount", "500", "500.00"),
        ("amount", "9000", "4500.00"),  # never below 0
        ("percent", "10", "450.00"),
        ("percent", "12.5", "562.50"),
        ("percent", "150", "4500.00"),
    ],
)
def test_discount_amount(kind, value, off) -> None:
    assert discount_amount(Decimal("4500"), kind, Decimal(value)) == Decimal(off)


@pytest.mark.django_db
def test_monthly_fee_with_real_numbers(fees_school) -> None:
    """Tuition 4,500 with 10% off = 4,050; Lab 1,000 with 1,500 off = 0;
    Transport 2,000 = 2,000. Monthly fee 6,050."""
    student = fees_school.student_1
    give_plan(student, add_plan(fees_school), "percent", "10")
    give_plan(student, add_plan(fees_school, "Lab", "1000"), "amount", "1500")
    give_plan(student, add_plan(fees_school, "Transport", "2000"))
    assert _in(fees_school, monthly_fee, student) == Decimal("6050.00")
    lines = _in(fees_school, fee_lines, student)
    assert [(line.name, line.discount, line.net) for line in lines] == [
        ("Lab", Decimal("1000.00"), Decimal("0.00")),
        ("Transport", Decimal("0.00"), Decimal("2000.00")),
        ("Tuition", Decimal("450.00"), Decimal("4050.00")),
    ]
    assert _in(fees_school, monthly_fee, fees_school.student_2) == Decimal("0.00")


def test_money_format() -> None:
    class Institute:
        currency_symbol = "Rs"

    assert money(Decimal("4500"), Institute()) == "Rs 4,500"
    assert money(Decimal("4500.5"), Institute()) == "Rs 4,500.50"
    assert money(None, Institute()) == "-"


# Scopes


@pytest.mark.django_db
def test_scopes(fees_school, admin, anonymous_user) -> None:
    plan = add_plan(fees_school)
    give_plan(fees_school.student_1, plan)
    assert not FeePlan.objects.exists()  # no tenant context
    assert not StudentFeePlan.objects.for_user(anonymous_user).exists()
    with tenant_context(admin.institute):
        for user, plans, rows in (
            (admin, 1, 1),
            (fees_school.teacher_1.user, 0, 0),
            (fees_school.student_1.user, 0, 1),
            (fees_school.student_2.user, 0, 0),
            (fees_school.guardian_1.user, 0, 1),
            (fees_school.guardian_2.user, 0, 0),
        ):
            assert FeePlan.objects.for_user(user).count() == plans, user
            assert StudentFeePlan.objects.for_user(user).count() == rows, user
    with tenant_context(fees_school.teacher_b.institute):
        assert not StudentFeePlan.objects.for_user(fees_school.student_b.user).exists()


# Pages


@pytest.mark.django_db
def test_list_add_edit_and_deactivate(fees_school, admin) -> None:
    client = signed_in(admin)
    assert "No fee plans yet." in client.get(LIST).content.decode()
    response = client.post(
        reverse("admin:fee_plan_create"), {"name": "Tuition", "amount": "4500"}
    )
    assert response["Location"] == LIST
    plan = FeePlan.unscoped.get()
    give_plan(fees_school.student_1, plan)
    html = client.get(LIST).content.decode()
    assert "Rs 4,500" in html and ">1<" in html and "Active" in html
    edit = reverse("admin:fee_plan_edit", kwargs={"pk": plan.pk})
    html = client.post(edit, {"name": "tuition", "amount": "0"}).content.decode()
    assert "Ensure this value is greater than or equal to 0.01." in html
    client.post(edit, {"name": "Tuition", "amount": "5000"})
    plan.refresh_from_db()
    assert plan.amount == Decimal("5000.00")
    status = reverse("admin:fee_plan_status", kwargs={"pk": plan.pk})
    client.post(status, {"action": "deactivate"})
    plan.refresh_from_db()
    assert plan.is_active is False


@pytest.mark.django_db
def test_other_institute_plan_is_404(fees_school, admin) -> None:
    other = add_plan(fees_school)
    # unscoped: test set-up outside a tenant context.
    FeePlan.unscoped.filter(pk=other.pk).update(
        institute=fees_school.teacher_b.institute
    )
    client = signed_in(admin)
    assert (
        client.get(reverse("admin:fee_plan_edit", kwargs={"pk": other.pk})).status_code
        == 404
    )


@pytest.mark.django_db
def test_basic_plan_has_no_fees(school) -> None:
    admin = make_user(
        email="admin-a@example.com",
        role=Role.INSTITUTE_ADMIN,
        institute=school.morning.institute,
    )
    assert signed_in(admin).get(LIST).status_code == 403


@pytest.mark.django_db
def test_sub_admin_needs_the_institute_menu(fees_school) -> None:
    institute = fees_school.morning.institute
    sub = make_user(email="sub@example.com", role=Role.SUB_ADMIN, institute=institute)
    request = RequestFactory().get(LIST)
    request.user, request.institute = sub, institute
    sub.allowed_menus = ["institute"]
    with tenant_context(institute):
        assert FeePlanListPage.as_view()(request).status_code == 200
    sub.allowed_menus = ["people"]
    assert FeePlanListPage.as_view()(request).status_code == 403


# Settings (owner decisions 2026-10-16)


@pytest.mark.django_db
def test_late_fee_and_academic_year_settings(fees_school, admin) -> None:
    from tests.institutes.test_settings_views import _settings_payload

    url = reverse("admin:institute_settings")
    client = signed_in(admin)
    client.post(url, _settings_payload(late_fee="250", academic_year_start_month="8"))
    settings = admin.institute.settings
    settings.refresh_from_db()
    assert (settings.late_fee, settings.academic_year_start_month) == (
        Decimal("250.00"),
        8,
    )
    html = client.post(url, _settings_payload(late_fee="-5")).content.decode()
    assert "Late fee must be between 0 and 100,000." in html
