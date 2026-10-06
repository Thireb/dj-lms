"""Plan feature keys (ARCHITECTURE section 5)."""

from __future__ import annotations

FEES = "fees"
PAYROLL = "payroll"
WHITEBOARD = "whiteboard"
LEAVE = "leave"
HOMEWORK = "homework"
LESSON_PLANS = "lesson_plans"
MESSAGING = "messaging"
TIME_ZONE_LECTURES = "time_zone_lectures"

ALL_FEATURE_KEYS: tuple[str, ...] = (
    FEES,
    PAYROLL,
    WHITEBOARD,
    LEAVE,
    HOMEWORK,
    LESSON_PLANS,
    MESSAGING,
    TIME_ZONE_LECTURES,
)

# FEATURES.md marks fees, payroll, planning and leave as Premium (verify split).
BASIC_PLAN_FEATURES: frozenset[str] = frozenset({MESSAGING, TIME_ZONE_LECTURES})

PREMIUM_PLAN_FEATURES: frozenset[str] = frozenset(ALL_FEATURE_KEYS)

PLAN_CODE_BASIC = "basic"
PLAN_CODE_PREMIUM = "premium"
