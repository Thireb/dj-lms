from decimal import Decimal

import pytest
from apps.finance.words import amount_in_words, number_in_words


@pytest.mark.parametrize(
    ("number", "words"),
    [
        (0, "zero"),
        (7, "seven"),
        (19, "nineteen"),
        (40, "forty"),
        (99, "ninety-nine"),
        (100, "one hundred"),
        (405, "four hundred five"),
        (1000, "one thousand"),
        (5050, "five thousand fifty"),
        (12345, "twelve thousand three hundred forty-five"),
        (1000000, "one million"),
        (2500750, "two million five hundred thousand seven hundred fifty"),
    ],
)
def test_number_in_words(number, words) -> None:
    assert number_in_words(number) == words


def test_amount_in_words() -> None:
    assert amount_in_words(Decimal("5050")) == "Five thousand fifty rupees only"
    assert amount_in_words(Decimal("4500.5")) == (
        "Four thousand five hundred rupees and fifty paisa only"
    )
