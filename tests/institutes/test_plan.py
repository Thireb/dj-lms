"""Plan model and seed data."""

from __future__ import annotations

import pytest
from apps.core.features import BASIC_PLAN_FEATURES, PLAN_CODE_BASIC
from apps.institutes.models import Plan


@pytest.mark.django_db
def test_plan_seed_basic_features() -> None:
    plan = Plan.objects.get(code=PLAN_CODE_BASIC)
    assert frozenset(plan.feature_keys) == BASIC_PLAN_FEATURES


@pytest.mark.django_db
def test_basic_plan_has_only_basic_features() -> None:
    plan = Plan.objects.get(code=PLAN_CODE_BASIC)
    assert sorted(plan.feature_keys) == ["messaging", "time_zone_lectures"]
    assert BASIC_PLAN_FEATURES == {"messaging", "time_zone_lectures"}
