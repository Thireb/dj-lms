"""Template filters for institute display."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django import template

register = template.Library()


@register.filter(name="currency")
def currency(amount: Any, institute: Any) -> str:
    symbol = getattr(institute, "currency_symbol", "") or ""
    if amount is None:
        return symbol
    if isinstance(amount, Decimal):
        text = f"{amount:.2f}"
    else:
        text = str(amount)
    return f"{symbol} {text}".strip()
