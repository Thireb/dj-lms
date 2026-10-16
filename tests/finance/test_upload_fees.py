"""Roadmap 7.1 part 3: the fee_plans and discount columns of the bulk
upload (SPEC 5). A percent applies to every plan; an amount to the first
plan (assumed)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from apps.core.tenancy import tenant_context
from apps.finance.models import StudentFeePlan
from apps.people.bulk_upload import TEMPLATE_COLUMNS, import_rows

from tests.finance.conftest import add_plan
from tests.people.test_bulk_upload_service import _check, _read
from tests.people.xlsx import row


def _choices(check) -> list[tuple[str, str, Decimal]]:
    return [
        (choice.plan.name, choice.discount_type, Decimal(choice.discount))
        for choice in check.fee_choices
    ]


def test_template_has_the_fee_columns() -> None:
    assert TEMPLATE_COLUMNS.index("fee_plans") == TEMPLATE_COLUMNS.index("subjects") + 1
    assert "discount" in TEMPLATE_COLUMNS


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("discount", "expected"),
    [
        ("", [("Tuition", "none", Decimal(0)), ("Lab", "none", Decimal(0))]),
        ("10%", [("Tuition", "percent", Decimal(10)), ("Lab", "percent", Decimal(10))]),
        ("500", [("Tuition", "amount", Decimal(500)), ("Lab", "none", Decimal(0))]),
    ],
)
def test_fee_plans_and_discounts(fees_school, discount, expected) -> None:
    add_plan(fees_school)
    add_plan(fees_school, "Lab", "1000")
    (check,) = _check(fees_school, row(fee_plans="tuition, Lab", discount=discount))
    assert check.ok, check.errors
    assert _choices(check) == expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("values", "error"),
    [
        ({"fee_plans": ""}, "Missing: fee_plans."),
        ({"fee_plans": "Bus"}, "Unknown or inactive fee plan: Bus."),
        ({"fee_plans": "Tuition", "discount": "ten"}, "discount: write a percent"),
        (
            {"fee_plans": "Tuition", "discount": "120%"},
            "discount: A percent discount is 0 to 100.",
        ),
        (
            {"fee_plans": "Tuition", "discount": "9000"},
            "discount: An amount discount is 0 to",
        ),
    ],
)
def test_fee_errors(fees_school, values, error) -> None:
    add_plan(fees_school)
    (check,) = _check(fees_school, row(**values))
    assert any(message.startswith(error) for message in check.errors), check.errors


@pytest.mark.django_db
def test_import_saves_the_plans(fees_school) -> None:
    add_plan(fees_school)
    institute = fees_school.morning.institute
    rows = _read([row(fee_plans="Tuition", discount="10%")])
    with tenant_context(institute):
        result = import_rows(institute, rows)
    assert result.codes and not result.failed
    plan = StudentFeePlan.unscoped.get()  # unscoped: test assertion
    assert (plan.fee_plan.name, plan.discount_type, plan.discount) == (
        "Tuition",
        "percent",
        Decimal("10.00"),
    )


@pytest.mark.django_db
def test_without_fees_the_columns_are_ignored(school) -> None:
    (check,) = _check(school, row(fee_plans="Anything", discount="ten"))
    assert check.ok and check.fee_choices is None
