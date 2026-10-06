"""Plan feature key registry (roadmap 1.2 / M6)."""

from __future__ import annotations

from apps.core import features


def test_basic_plan_is_subset_of_premium() -> None:
    assert features.BASIC_PLAN_FEATURES <= features.PREMIUM_PLAN_FEATURES


def test_all_feature_keys_listed() -> None:
    assert set(features.ALL_FEATURE_KEYS) == features.PREMIUM_PLAN_FEATURES
