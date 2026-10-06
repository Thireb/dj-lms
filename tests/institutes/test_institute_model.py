"""Institute campus fields and features property."""

from __future__ import annotations

import pytest
from apps.core.features import FEES, PAYROLL
from apps.institutes.models import Institute, Plan


@pytest.mark.django_db
def test_institute_features_from_plan(basic_plan: Plan) -> None:
    institute = Institute.objects.create(name="Demo", plan=basic_plan)
    assert FEES in institute.features
    assert PAYROLL not in institute.features
