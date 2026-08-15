"""Typed failures exposed by the financial domain."""


class DomainError(ValueError):
    """Base class for an expected, user-visible domain failure."""


class InvalidMoney(DomainError):
    """A monetary value is not exact or its currency is invalid."""


class CurrencyMismatch(DomainError):
    """An operation attempted to mix currencies without an FX snapshot."""


class InvalidAllocationInput(DomainError):
    """Aggregate portfolio inputs cannot produce a trustworthy plan."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")
