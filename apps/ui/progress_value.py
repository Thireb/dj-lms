"""Normalize ProgressBar width values for safe CSS interpolation."""

from __future__ import annotations

import math


def clamp_progress_value(value: object) -> int | float:
    """Coerce ``value`` to a number in ``0..100``; invalid input becomes ``0``."""
    try:
        if isinstance(value, bool):
            num = float(int(value))
        elif isinstance(value, (int, float)):
            num = float(value)
        elif value is None:
            num = 0.0
        else:
            num = float(str(value).strip())
    except (TypeError, ValueError):
        return 0
    if math.isnan(num) or math.isinf(num):
        return 0
    clamped = max(0.0, min(100.0, num))
    if clamped == int(clamped):
        return int(clamped)
    return clamped
