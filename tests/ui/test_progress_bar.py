from __future__ import annotations

import math

import pytest
from apps.ui.components.data import ProgressBar


@pytest.mark.parametrize(
    "value,expected_width",
    [
        (50, "50"),
        (150, "100"),
        (-5, "0"),
        ("abc", "0"),
        (None, "0"),
        (float("nan"), "0"),
        ("50;background:red", "0"),
    ],
)
def test_progress_bar_clamps_value_in_style(value: object, expected_width: str) -> None:
    html = str(ProgressBar(value, label="Test"))
    assert f'style="width: {expected_width}%"' in html
    assert "background:red" not in html
    assert "abc" not in html


def test_progress_bar_accepts_float_in_range() -> None:
    html = str(ProgressBar(33.5, label="Partial"))
    assert 'style="width: 33.5%"' in html
    assert not math.isnan(33.5)
