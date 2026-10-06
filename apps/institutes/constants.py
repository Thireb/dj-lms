"""Institute-wide choice constants."""

from __future__ import annotations

CURRENCY_CHOICES: tuple[tuple[str, str], ...] = (
    ("PKR", "Pakistani rupee (PKR)"),
    ("USD", "US dollar (USD)"),
    ("GBP", "British pound (GBP)"),
    ("EUR", "Euro (EUR)"),
    ("AED", "UAE dirham (AED)"),
    ("SAR", "Saudi riyal (SAR)"),
)

CURRENCY_SYMBOLS: dict[str, str] = {
    "PKR": "Rs",
    "USD": "$",
    "GBP": "£",
    "EUR": "€",
    "AED": "د.إ",
    "SAR": "﷼",
}
