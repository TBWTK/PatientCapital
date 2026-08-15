"""Exact currency-aware money values."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from patientcapital.domain.errors import CurrencyMismatch, InvalidMoney

MINOR_UNIT = Decimal("0.01")
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


def quantize_minor(value: Decimal) -> Decimal:
    """Round an explicitly calculated value to the MVP two-decimal minor unit."""

    if not isinstance(value, Decimal) or not value.is_finite():
        raise InvalidMoney("money amount must be a finite Decimal")
    return value.quantize(MINOR_UNIT, rounding=ROUND_HALF_UP)


def validate_currency(currency: str) -> None:
    if not isinstance(currency, str) or _CURRENCY_PATTERN.fullmatch(currency) is None:
        raise InvalidMoney("currency must be an uppercase ISO-like three-letter code")


@dataclass(frozen=True, slots=True)
class Money:
    """An immutable exact amount; calculations must round before construction."""

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        validate_currency(self.currency)
        if not isinstance(self.amount, Decimal) or not self.amount.is_finite():
            raise InvalidMoney("money amount must be a finite Decimal")
        if self.amount != self.amount.quantize(MINOR_UNIT):
            raise InvalidMoney("money amount exceeds the currency minor unit")
        object.__setattr__(self, "amount", self.amount.quantize(MINOR_UNIT))

    @classmethod
    def zero(cls, currency: str) -> Money:
        return cls(Decimal("0.00"), currency)

    @classmethod
    def calculated(cls, amount: Decimal, currency: str) -> Money:
        return cls(quantize_minor(amount), currency)

    def _require_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatch(f"cannot mix {self.currency} and {other.currency}")

    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_currency(other)
        return Money(self.amount - other.amount, self.currency)
