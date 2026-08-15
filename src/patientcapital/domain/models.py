"""Immutable contracts for a contribution planning run."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from patientcapital.domain.errors import InvalidAllocationInput
from patientcapital.domain.money import Money, validate_currency


def _finite_decimal(value: Decimal, *, code: str, positive: bool = False) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise InvalidAllocationInput(code, "value must be a finite Decimal")
    if positive and value <= 0:
        raise InvalidAllocationInput(code, "value must be greater than zero")


@dataclass(frozen=True, slots=True)
class Asset:
    id: str
    name: str
    currency: str
    lot_size: int

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.name.strip():
            raise InvalidAllocationInput("INVALID_ASSET", "asset id and name are required")
        validate_currency(self.currency)
        if (
            isinstance(self.lot_size, bool)
            or not isinstance(self.lot_size, int)
            or self.lot_size <= 0
        ):
            raise InvalidAllocationInput("INVALID_LOT_SIZE", f"invalid lot for {self.id}")


@dataclass(frozen=True, slots=True)
class PriceSnapshot:
    asset_id: str
    price: Decimal
    currency: str
    as_of: datetime
    max_age: timedelta
    source: str

    def __post_init__(self) -> None:
        if not self.asset_id.strip() or not self.source.strip():
            raise InvalidAllocationInput("INVALID_PRICE", "asset id and source are required")
        _finite_decimal(self.price, code="INVALID_PRICE", positive=True)
        validate_currency(self.currency)
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise InvalidAllocationInput(
                "INVALID_PRICE_TIME", "price timestamp must be timezone-aware"
            )
        if self.max_age <= timedelta(0):
            raise InvalidAllocationInput("INVALID_PRICE_MAX_AGE", "max age must be positive")


@dataclass(frozen=True, slots=True)
class Position:
    asset_id: str
    quantity: int

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise InvalidAllocationInput("INVALID_POSITION", "asset id is required")
        if (
            isinstance(self.quantity, bool)
            or not isinstance(self.quantity, int)
            or self.quantity < 0
        ):
            raise InvalidAllocationInput(
                "INVALID_POSITION_QUANTITY", f"quantity for {self.asset_id} must be non-negative"
            )


@dataclass(frozen=True, slots=True)
class TargetAllocation:
    asset_id: str
    weight: Decimal

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise InvalidAllocationInput("INVALID_TARGET", "asset id is required")
        _finite_decimal(self.weight, code="INVALID_TARGET")
        if self.weight < 0 or self.weight > 1:
            raise InvalidAllocationInput(
                "INVALID_TARGET_WEIGHT", f"weight for {self.asset_id} must be between zero and one"
            )


@dataclass(frozen=True, slots=True)
class FeePolicy:
    rate: Decimal
    minimum: Money

    def __post_init__(self) -> None:
        _finite_decimal(self.rate, code="INVALID_FEE_RATE")
        if self.rate < 0 or self.rate > 1:
            raise InvalidAllocationInput(
                "INVALID_FEE_RATE", "fee rate must be between zero and one"
            )
        if self.minimum.amount < 0:
            raise InvalidAllocationInput("INVALID_MINIMUM_FEE", "minimum fee must be non-negative")


@dataclass(frozen=True, slots=True)
class AllocationInput:
    contribution: Money
    cash_buffer: Money
    assets: tuple[Asset, ...]
    prices: tuple[PriceSnapshot, ...]
    positions: tuple[Position, ...]
    targets: tuple[TargetAllocation, ...]
    fee_policy: FeePolicy
    calculated_at: datetime


class PlanReason(StrEnum):
    ALLOCATED = "ALLOCATED"
    BUDGET_BELOW_ANY_LOT = "BUDGET_BELOW_ANY_LOT"
    ZERO_INVESTABLE = "ZERO_INVESTABLE"


@dataclass(frozen=True, slots=True)
class PlanLine:
    asset_id: str
    lots: int
    lot_size: int
    quantity: int
    unit_price: Decimal
    current_value: Money
    target_value: Money
    pre_drift: Money
    post_drift: Money
    gross: Money
    fee: Money
    total: Money


@dataclass(frozen=True, slots=True)
class RecommendationPlan:
    algorithm_version: str
    input_hash: str
    calculated_at: datetime
    investable: Money
    gross: Money
    fees: Money
    spent: Money
    leftover: Money
    reason: PlanReason
    lines: tuple[PlanLine, ...]
