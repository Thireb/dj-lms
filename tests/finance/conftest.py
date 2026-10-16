from __future__ import annotations

from decimal import Decimal

import pytest
from apps.core.features import ALL_FEATURE_KEYS
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.finance.models import FeePlan, StudentFeePlan
from apps.institutes.models import Plan

from tests.conftest import make_user


@pytest.fixture
def fees_school(school):
    """The school on a plan with every feature (fees is Premium)."""
    institute = school.morning.institute
    institute.plan = Plan.objects.create(
        code="all-features", name="All", feature_keys=list(ALL_FEATURE_KEYS)
    )
    institute.save()
    return school


@pytest.fixture
def admin(fees_school):
    return make_user(
        email="admin-a@example.com",
        role=Role.INSTITUTE_ADMIN,
        institute=fees_school.morning.institute,
    )


def add_plan(school, name="Tuition", amount="4500") -> FeePlan:
    institute = school.morning.institute
    # unscoped: test set-up outside a tenant context.
    return FeePlan.unscoped.create(
        institute=institute, name=name, amount=Decimal(amount)
    )


def give_plan(student, plan, discount_type="none", discount="0") -> StudentFeePlan:
    with tenant_context(student.institute):
        return StudentFeePlan.objects.create(
            institute=student.institute,
            student=student,
            fee_plan=plan,
            discount_type=discount_type,
            discount=Decimal(discount),
        )
