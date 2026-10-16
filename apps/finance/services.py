"""Fee rules (roadmap Phase 7, SPEC 6.1). Every function runs in the
institute's tenant context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from apps.core.tenancy import require_tenant_context
from apps.finance.models import (
    MAX_AMOUNT,
    Challan,
    ChallanLine,
    ChallanStatus,
    DiscountType,
    FeePlan,
    StudentFeePlan,
)
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


@dataclass(frozen=True)
class FeeChoice:
    """One plan chosen on Enrol or Edit, with its discount."""

    plan: FeePlan
    discount_type: str = DiscountType.NONE
    discount: Decimal = Decimal("0")


NO_PLAN = "Choose at least one fee plan."


def check_fee_choices(choices: list[FeeChoice], current: set[int]) -> dict[str, str]:
    """Errors by plan pk (and "" for the whole list). An inactive plan may
    stay on a student who has it (``current``); it is not offered anew."""
    errors: dict[str, str] = {}
    if not choices:
        errors[""] = NO_PLAN
    for choice in choices:
        plan, value = choice.plan, choice.discount
        key = str(plan.pk)
        if not plan.is_active and plan.pk not in current:
            errors[key] = f"{plan.name} is inactive."
        elif choice.discount_type == DiscountType.PERCENT and not 0 <= value <= 100:
            errors[key] = "A percent discount is 0 to 100."
        elif (
            choice.discount_type == DiscountType.AMOUNT
            and not 0 <= value <= plan.amount
        ):
            errors[key] = f"An amount discount is 0 to {plan.amount}."
        elif choice.discount_type not in DiscountType.values:
            errors[key] = "Choose a discount type."
    return errors


def set_student_fee_plans(student: Any, choices: list[FeeChoice]) -> None:
    """Replace the student's fee plans (SPEC 4.1: at least one plan). Runs
    inside the caller's transaction."""
    require_tenant_context(student.institute)
    rows = StudentFeePlan.objects.filter(student=student)
    current = set(rows.values_list("fee_plan_id", flat=True))
    errors = check_fee_choices(choices, current)
    if errors:
        raise ValidationError({"fee_plans": list(errors.values())})
    rows.exclude(fee_plan__in=[choice.plan for choice in choices]).delete()
    for choice in choices:
        no_discount = choice.discount_type == DiscountType.NONE
        StudentFeePlan.objects.update_or_create(
            institute=student.institute,
            student=student,
            fee_plan=choice.plan,
            defaults={
                "discount_type": choice.discount_type,
                "discount": Decimal("0") if no_discount else to_money(choice.discount),
            },
        )


def monthly_fees(students: list[Any]) -> dict[int, Decimal]:
    """The monthly fee of each student on a page, in one query."""
    totals = {student.pk: Decimal("0.00") for student in students}
    rows = StudentFeePlan.objects.filter(student__in=students).select_related(
        "fee_plan"
    )
    for row in rows:
        amount = row.fee_plan.amount
        off = discount_amount(amount, row.discount_type, row.discount)
        totals[row.student_id] += amount - off
    return totals


# Challans (roadmap 7.2, SPEC 4.7 and 6.1)

NO_FEE = "No fee plan"
CANCEL_PAID = "A challan with payments cannot be cancelled."


def month_start(day: date) -> date:
    return day.replace(day=1)


def default_due_date(institute: Any, month: date) -> date:
    """The "Fee due day" setting in the challan's month (SPEC 3 settings)."""
    return month.replace(day=institute.settings.fee_due_day)


def challan_key(month: date) -> str:
    """The number sequence of a month: CH202610 (8 characters)."""
    return f"CH{month:%Y%m}"


@dataclass(frozen=True)
class PlannedChallan:
    student: Any
    lines: list[FeeLine]

    @property
    def amount(self) -> Decimal:
        return sum((line.net for line in self.lines), Decimal("0.00"))


@dataclass(frozen=True)
class ChallanPreview:
    planned: list[PlannedChallan]
    skipped: list[tuple[Any, str]]  # (student, why)


def _lines_by_student(students: list[Any]) -> dict[int, list[FeeLine]]:
    lines: dict[int, list[FeeLine]] = {student.pk: [] for student in students}
    rows = (
        StudentFeePlan.objects.filter(student__in=students)
        .select_related("fee_plan")
        .order_by("fee_plan__name")
    )
    for row in rows:
        amount = row.fee_plan.amount
        off = discount_amount(amount, row.discount_type, row.discount)
        lines[row.student_id].append(
            FeeLine(row.fee_plan.name, amount, off, amount - off)
        )
    return lines


def preview_challans(month: date, students: list[Any]) -> ChallanPreview:
    """Who gets a challan for the month. Skipped: a student who already has
    a challan that is not cancelled (SPEC 4.7), or has no fee plan."""
    month = month_start(month)
    existing = dict(
        Challan.objects.filter(student__in=students, month=month)
        .exclude(status=ChallanStatus.CANCELLED)
        .values_list("student_id", "number")
    )
    lines = _lines_by_student(students)
    planned, skipped = [], []
    for student in students:
        if student.pk in existing:
            skipped.append((student, f"Has {existing[student.pk]}"))
        elif not lines[student.pk]:
            skipped.append((student, NO_FEE))
        else:
            planned.append(PlannedChallan(student, lines[student.pk]))
    return ChallanPreview(planned, skipped)


def check_challan_dates(month: date, due_date: date, today: date) -> None:
    if due_date < today:
        raise ValidationError({"due_date": "Choose a due date today or later."})
    if due_date < month_start(month):
        raise ValidationError({"due_date": "The due date cannot be before the month."})


def generate_challans(
    institute: Any,
    month: date,
    due_date: date,
    students: list[Any],
    *,
    today: date | None = None,
) -> list[Challan]:
    """Make the challans of a month (SPEC 4.7). The skip rule is checked
    again, so a second run or a double click makes no duplicates. Each
    challan is saved in its own transaction."""
    # people.services imports this module (fee plans on Enrol), so import here.
    from apps.people.services import next_number

    require_tenant_context(institute)
    today = today or timezone.localdate()
    month = month_start(month)
    check_challan_dates(month, due_date, today)
    made = []
    for plan in preview_challans(month, students).planned:
        try:
            with transaction.atomic():
                number = next_number(institute, challan_key(month))
                challan = Challan.objects.create(
                    institute=institute,
                    student=plan.student,
                    number=f"CH-{month:%Y%m}-{number:04d}",
                    month=month,
                    issue_date=today,
                    due_date=due_date,
                    amount=plan.amount,
                )
                ChallanLine.objects.bulk_create(
                    ChallanLine(
                        institute=institute,
                        challan=challan,
                        name=line.name,
                        amount=line.amount,
                        discount=line.discount,
                    )
                    for line in plan.lines
                )
        except IntegrityError:
            continue  # made meanwhile by another run: the skip rule again
        made.append(challan)
    return made


def cancel_challan(challan: Challan) -> Challan:
    """SPEC 6.1: a challan with payments cannot be cancelled."""
    with transaction.atomic():
        locked = Challan.objects.select_for_update().get(pk=challan.pk)
        if locked.paid > 0:
            raise ValidationError(CANCEL_PAID)
        if locked.status == ChallanStatus.CANCELLED:
            return locked
        locked.status = ChallanStatus.CANCELLED
        locked.save(update_fields=["status"])
        return locked


def is_overdue(challan: Challan, today: date | None = None) -> bool:
    """SPEC 6.1: pending or partial, and today is after the due date."""
    today = today or timezone.localdate()
    open_ = challan.status in (ChallanStatus.PENDING, ChallanStatus.PARTIAL)
    return open_ and today > challan.due_date


OVERDUE = "overdue"  # a filter value: shown, not stored


def list_challans(
    user: Any,
    *,
    month: date | None = None,
    batch_id: int | None = None,
    status: str = "",
    search: str = "",
    today: date | None = None,
) -> QuerySet[Challan]:
    rows = Challan.objects.for_user(user).select_related("student__user")
    if month:
        rows = rows.filter(month=month_start(month))
    if batch_id:
        rows = rows.filter(student__batch_subjects__batch_id=batch_id).distinct()
    if status == OVERDUE:
        today = today or timezone.localdate()
        rows = rows.filter(
            status__in=[ChallanStatus.PENDING, ChallanStatus.PARTIAL],
            due_date__lt=today,
        )
    elif status in ChallanStatus.values:
        rows = rows.filter(status=status)
    for word in search.split()[:3]:
        rows = rows.filter(
            Q(number__icontains=word)
            | Q(student__student_code__icontains=word)
            | Q(student__user__first_name__icontains=word)
            | Q(student__user__last_name__icontains=word)
        )
    return rows.order_by("-month", "-number")
