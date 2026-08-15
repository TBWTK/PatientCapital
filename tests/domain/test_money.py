from decimal import Decimal

import pytest

from patientcapital.domain.errors import CurrencyMismatch, InvalidMoney
from patientcapital.domain.money import Money


def test_money_is_immutable_exact_and_adds_only_same_currency() -> None:
    amount = Money(Decimal("10.25"), "RUB")

    assert amount + Money(Decimal("1.75"), "RUB") == Money(Decimal("12.00"), "RUB")
    assert amount - Money(Decimal("0.25"), "RUB") == Money(Decimal("10.00"), "RUB")

    with pytest.raises(CurrencyMismatch, match=r"RUB.*USD"):
        _ = amount + Money(Decimal("1.00"), "USD")


@pytest.mark.parametrize(
    ("value", "currency"),
    [
        (Decimal("NaN"), "RUB"),
        (Decimal("Infinity"), "RUB"),
        (Decimal("1.001"), "RUB"),
        (Decimal("1.00"), "rub"),
        (Decimal("1.00"), "RU"),
    ],
)
def test_money_rejects_ambiguous_values(value: Decimal, currency: str) -> None:
    with pytest.raises(InvalidMoney):
        Money(value, currency)


def test_money_does_not_silently_round() -> None:
    with pytest.raises(InvalidMoney, match="minor unit"):
        Money(Decimal("10.999"), "RUB")
