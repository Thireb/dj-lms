"""Fee rules (roadmap Phase 7, SPEC 6.1). Every function runs in the
institute's tenant context."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q, QuerySet

from apps.core.tenancy import require_tenant_context
from apps.finance.models import MAX_AMOUNT, DiscountType, FeePlan, StudentFeePlan
from apps.people.models import ProfileStatus

CENT = Decimal("0.01")


def to_money(value: Any) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


# Fee plans (SPEC 4.4)


def _check_plan(
    institute: Any, name: str, amount: Decimal, plan: FeePlan | None
) -> str:
    errors: dict[str, str] = {}
    name = name.strip()
    if not name:
        errors["name"] = "Write a name."
    else:
        same = FeePlan.objects.filter(name__iexact=name)
        if plan is not None:
            same = same.exclude(pk=plan.pk)
        if same.exists():
            errors["name"] = "A fee plan with this name already exists."
    if not Decimal("0") < amount <= MAX_AMOUNT:
        errors["amount"] = "The amount must be more than 0."
    if errors:
        raise ValidationError(errors)
    return name


@transaction.atomic
def create_fee_plan(institute: Any, *, name: str, amount: Decimal) -> FeePlan:
    require_tenant_context(institute)
    name = _check_plan(institute, name, amount, None)
    return FeePlan.objects.create(
        institute=institute, name=name, amount=to_money(amount)
    )


@transaction.atomic
def update_fee_plan(plan: FeePlan, *, name: str, amount: Decimal) -> FeePlan:
    """A new amount counts for challans made from now on; old challans keep
    theirs (SPEC 6.1: the amount is frozen on the challan)."""
    require_tenant_context(plan.institute)
    plan.name = _check_plan(plan.institute, name, amount, plan)
    plan.amount = to_money(amount)
    plan.save(update_fields=["name", "amount"])
    return plan


def set_fee_plan_active(plan: FeePlan, *, is_active: bool) -> FeePlan:
    """An inactive plan is not offered on new enrolments; students who have
    it keep it."""
    plan.is_active = is_active
    plan.save(update_fields=["is_active"])
    return plan


def list_fee_plans(user: Any, search: str = "") -> QuerySet[FeePlan]:
    rows = FeePlan.objects.for_user(user)
    if search:
        rows = rows.filter(name__icontains=search)
    active = Q(students__student__status=ProfileStatus.ACTIVE)
    return rows.annotate(student_count=Count("students", filter=active)).order_by(
        "-is_active", "name"
    )


# A student's monthly fee (SPEC 6.1)


@dataclass(frozen=True)
class FeeLine:
    """One fee plan on a student: its amount, the discount and what is left."""

    name: str
    amount: Decimal
    discount: Decimal
    net: Decimal


def discount_amount(amount: Decimal, discount_type: str, value: Decimal) -> Decimal:
    """The money taken off one plan. A percent applies to that plan only;
    a discount never makes a line negative."""
    if discount_type == DiscountType.PERCENT:
        off = amount * min(value, Decimal(100)) / Decimal(100)
    elif discount_type == DiscountType.AMOUNT:
        off = value
    else:
        off = Decimal(0)
    return to_money(min(max(off, Decimal(0)), amount))


def fee_lines(student: Any) -> list[FeeLine]:
    rows = StudentFeePlan.objects.filter(student=student).select_related("fee_plan")
    lines = []
    for row in rows.order_by("fee_plan__name"):
        amount = row.fee_plan.amount
        off = discount_amount(amount, row.discount_type, row.discount)
        lines.append(FeeLine(row.fee_plan.name, amount, off, amount - off))
    return lines


def monthly_fee(student: Any) -> Decimal:
    """Monthly fee = the plans minus their discounts (SPEC 6.1)."""
    return sum((line.net for line in fee_lines(student)), Decimal("0.00"))
