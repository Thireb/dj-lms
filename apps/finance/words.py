"""Amounts in words for printed challans and receipts (SPEC 9.1: "amount in
words"). The international system (thousand, million), assumed."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

ONES = (
    "zero one two three four five six seven eight nine ten eleven twelve "
    "thirteen fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
SCALES = ((10**9, "billion"), (10**6, "million"), (1000, "thousand"))


def _below_thousand(number: int) -> str:
    parts = []
    hundreds, rest = divmod(number, 100)
    if hundreds:
        parts.append(f"{ONES[hundreds]} hundred")
    if rest >= 20:
        tens, ones = divmod(rest, 10)
        parts.append(TENS[tens] + (f"-{ONES[ones]}" if ones else ""))
    elif rest or not parts:
        parts.append(ONES[rest])
    return " ".join(parts)


def number_in_words(number: int) -> str:
    """Example: 5050 -> "five thousand fifty"."""
    if number < 1000:
        return _below_thousand(number)
    parts = []
    for size, name in SCALES:
        count, number = divmod(number, size)
        if count:
            parts.append(f"{number_in_words(count)} {name}")
    if number:
        parts.append(_below_thousand(number))
    return " ".join(parts)


def amount_in_words(
    amount: Decimal, currency: str = "rupees", cents: str = "paisa"
) -> str:
    """Example: 5050.50 -> "Five thousand fifty rupees and fifty paisa only"."""
    amount = Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    whole = int(amount)
    fraction = int((amount - whole) * 100)
    text = f"{number_in_words(whole)} {currency}"
    if fraction:
        text += f" and {number_in_words(fraction)} {cents}"
    return f"{text} only".capitalize()
