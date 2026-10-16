"""Fees (roadmap Phase 7, FEATURES 8, SPEC 4.4, 4.7, 4.8, 4.17 and 6.1).

Money is ``Decimal`` with 2 places (AGENTS.md 4).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower

from apps.core.managers import TenantManager, TenantQuerySet, UnscopedTenantManager
from apps.core.models import TenantModel
from apps.core.roles import INSTITUTE_WIDE_ROLES, Role, user_role

MAX_AMOUNT = Decimal("10000000")  # 1 crore: a guard against typing mistakes
MONEY = {"max_digits": 12, "decimal_places": 2}

# From a student's fee row to the user who may see it, by role.
STUDENT_LOOKUPS = {
    Role.STUDENT: "student__user_id",
    Role.GUARDIAN: "student__guardian_links__guardian__user_id",
}


class AdminOnlyQuerySet(TenantQuerySet):
    """Admins and sub-admins see the institute; other roles nothing."""

    def for_user(self, user: Any) -> AdminOnlyQuerySet:
        scoped = super().for_user(user)
        return scoped if user_role(user) in INSTITUTE_WIDE_ROLES else scoped.none()


class StudentRowQuerySet(TenantQuerySet):
    """Admins see the institute, a student their own rows, a guardian the
    rows of their children; teachers nothing."""

    def for_user(self, user: Any) -> StudentRowQuerySet:
        scoped = super().for_user(user)
        role = user_role(user)
        if role in INSTITUTE_WIDE_ROLES:
            return scoped
        lookup = STUDENT_LOOKUPS.get(role or "")
        if lookup is None:
            return scoped.none()
        return scoped.filter(**{lookup: getattr(user, "pk", None)}).distinct()


class FeePlan(TenantModel):
    """A monthly fee, such as "Tuition" or "Lab" (SPEC 4.4)."""

    name = models.CharField(max_length=100)
    amount = models.DecimalField(
        **MONEY, validators=[MinValueValidator(Decimal("0.01"))]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager.from_queryset(AdminOnlyQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(AdminOnlyQuerySet)()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"), "institute", name="finance_feeplan_name_unique"
            )
        ]

    def __str__(self) -> str:
        return self.name


class DiscountType(models.TextChoices):
    NONE = "none", "No discount"
    AMOUNT = "amount", "Amount"
    PERCENT = "percent", "Percent"


class StudentFeePlan(TenantModel):
    """A fee plan on a student, with an optional discount per plan (SPEC 4.1:
    "amount or percent"; 6.1: percent discounts apply per plan)."""

    student = models.ForeignKey(
        "people.StudentProfile", on_delete=models.CASCADE, related_name="fee_plans"
    )
    fee_plan = models.ForeignKey(
        FeePlan, on_delete=models.PROTECT, related_name="students"
    )
    discount_type = models.CharField(
        max_length=8, choices=DiscountType.choices, default=DiscountType.NONE
    )
    discount = models.DecimalField(
        **MONEY,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(MAX_AMOUNT)],
    )

    objects = TenantManager.from_queryset(StudentRowQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(StudentRowQuerySet)()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "fee_plan"], name="finance_student_plan_once"
            )
        ]

    def __str__(self) -> str:
        return f"{self.student}: {self.fee_plan}"


class ChallanStatus(models.TextChoices):
    """SPEC 2. "Overdue" is shown, not stored (pending or partial past the
    due date)."""

    PENDING = "pending", "Pending"
    PARTIAL = "partial", "Partial"
    PAID = "paid", "Paid"
    CANCELLED = "cancelled", "Cancelled"


class Challan(TenantModel):
    """One student's bill for one month (SPEC 4.7 and 6.1). The amount and
    lines are frozen at generation; ``paid`` is the sum of its payments;
    ``late_fee`` is added once when it is not paid in full by the due date
    (owner decision 2026-10-16)."""

    student = models.ForeignKey(
        "people.StudentProfile", on_delete=models.PROTECT, related_name="challans"
    )
    number = models.CharField(max_length=20)
    month = models.DateField(help_text="The first day of the month it bills.")
    issue_date = models.DateField()
    due_date = models.DateField()
    amount = models.DecimalField(**MONEY)
    late_fee = models.DecimalField(**MONEY, default=Decimal("0"))
    paid = models.DecimalField(**MONEY, default=Decimal("0"))
    status = models.CharField(
        max_length=10, choices=ChallanStatus.choices, default=ChallanStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager.from_queryset(StudentRowQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(StudentRowQuerySet)()

    class Meta:
        ordering = ["-month", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["institute", "number"], name="finance_challan_number_unique"
            ),
            # SPEC 4.7: one challan per student and month, unless cancelled.
            models.UniqueConstraint(
                fields=["student", "month"],
                condition=~models.Q(status="cancelled"),
                name="finance_challan_one_per_month",
            ),
        ]
        indexes = [models.Index(fields=["institute", "month", "status"])]

    def __str__(self) -> str:
        return self.number

    @property
    def total(self) -> Decimal:
        """What the student owes in all: the amount and any late fee."""
        return self.amount + self.late_fee

    @property
    def balance(self) -> Decimal:
        return self.total - self.paid


class ChallanLine(TenantModel):
    """A fee plan line on a challan, as it was when the challan was made
    (SPEC 9.1: fee plan lines and discounts)."""

    challan = models.ForeignKey(Challan, on_delete=models.CASCADE, related_name="lines")
    name = models.CharField(max_length=100)
    amount = models.DecimalField(**MONEY)
    discount = models.DecimalField(**MONEY, default=Decimal("0"))

    objects = TenantManager.from_queryset(AdminOnlyQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(AdminOnlyQuerySet)()

    class Meta:
        ordering = ["pk"]

    def __str__(self) -> str:
        return self.name

    @property
    def net(self) -> Decimal:
        return self.amount - self.discount
