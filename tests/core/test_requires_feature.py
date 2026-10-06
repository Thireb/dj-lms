"""FeatureRequiredMixin and @requires_feature (roadmap 1.2)."""

from __future__ import annotations

import pytest
from apps.core.features import FEES
from apps.core.mixins.access import requires_feature
from apps.core.roles import Role
from apps.ui.views.pages import DashboardPage
from django.test import RequestFactory

from tests.conftest import make_user


@requires_feature(FEES)
class FeesDashboard(DashboardPage):
    portal = "admin"
    menu_key = "finance"
    allowed_roles = [Role.INSTITUTE_ADMIN]
    title = "Fees"


@pytest.mark.django_db
def test_requires_feature_allows_when_plan_includes_key(
    institute_a, institute_admin_user
) -> None:
    from apps.core.features import PLAN_CODE_PREMIUM
    from apps.institutes.models import Plan

    institute_a.plan = Plan.objects.get(code=PLAN_CODE_PREMIUM)
    institute_a.save()
    request = RequestFactory().get("/admin/fees/")
    request.user = institute_admin_user
    request.institute = institute_a
    response = FeesDashboard.as_view()(request)
    assert response.status_code == 200


@pytest.mark.django_db
def test_requires_feature_blocks_fees_on_basic_plan(
    institute_a, institute_admin_user
) -> None:
    request = RequestFactory().get("/admin/fees/")
    request.user = institute_admin_user
    request.institute = institute_a
    response = FeesDashboard.as_view()(request)
    assert response.status_code == 403


@pytest.mark.django_db
def test_requires_feature_blocks_when_plan_missing_key(institute_a) -> None:
    from apps.core.features import PLAN_CODE_PREMIUM
    from apps.institutes.models import Plan

    plan = Plan.objects.get(code=PLAN_CODE_PREMIUM)
    plan.feature_keys = []
    plan.save()
    institute_a.plan = plan
    institute_a.save()
    user = make_user(
        email="admin@example.com",
        role=Role.INSTITUTE_ADMIN,
        institute=institute_a,
    )
    request = RequestFactory().get("/admin/fees/")
    request.user = user
    request.institute = institute_a
    response = FeesDashboard.as_view()(request)
    assert response.status_code == 403
    assert b"Feature not available" in response.content
