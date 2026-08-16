"""Transport-neutral, immutable market facts consumed by discovery policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Protocol, runtime_checkable

from patientcapital.domain.errors import InvalidAllocationInput
from patientcapital.domain.money import validate_currency
from patientcapital.research.models import DividendResearchEvidence


class InstrumentKind(StrEnum):
    OFZ = "ofz"
    EQUITY_INDEX_FUND = "equity_index_fund"
    DIVIDEND_STOCK = "dividend_stock"
    PUBLIC_EQUITY = "public_equity"


def _finite(value: Decimal, *, name: str, positive: bool = False) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise InvalidAllocationInput("INVALID_MARKET_CANDIDATE", f"{name} must be finite Decimal")
    if positive and value <= 0:
        raise InvalidAllocationInput("INVALID_MARKET_CANDIDATE", f"{name} must be positive")


@dataclass(frozen=True, slots=True)
class LiquidityObservation:
    session_date: date
    turnover_rub: Decimal
    trades: int
    bid: Decimal | None = None
    offer: Decimal | None = None

    def __post_init__(self) -> None:
        _finite(self.turnover_rub, name="liquidity turnover")
        if self.turnover_rub < 0:
            raise InvalidAllocationInput(
                "INVALID_LIQUIDITY_EVIDENCE", "liquidity turnover cannot be negative"
            )
        if isinstance(self.trades, bool) or not isinstance(self.trades, int) or self.trades < 0:
            raise InvalidAllocationInput(
                "INVALID_LIQUIDITY_EVIDENCE", "liquidity trades must be non-negative integer"
            )
        if (self.bid is None) != (self.offer is None):
            raise InvalidAllocationInput(
                "INVALID_LIQUIDITY_EVIDENCE", "bid and offer must be supplied together"
            )
        if self.bid is not None and self.offer is not None:
            _finite(self.bid, name="liquidity bid", positive=True)
            _finite(self.offer, name="liquidity offer", positive=True)
            if self.offer < self.bid:
                raise InvalidAllocationInput(
                    "INVALID_LIQUIDITY_EVIDENCE", "offer cannot be below bid"
                )

    @property
    def spread_percent(self) -> Decimal | None:
        if self.bid is None or self.offer is None:
            return None
        midpoint = (self.bid + self.offer) / Decimal("2")
        return ((self.offer - self.bid) / midpoint * Decimal("100")).quantize(Decimal("0.00000001"))


@dataclass(frozen=True, slots=True)
class MarketLiquidityEvidence:
    policy_version: str
    observed_at: datetime
    max_age: timedelta
    security_status: str
    observations: tuple[LiquidityObservation, ...]
    source_url: str

    def __post_init__(self) -> None:
        if not self.policy_version.strip():
            raise InvalidAllocationInput(
                "INVALID_LIQUIDITY_EVIDENCE", "liquidity policy version is required"
            )
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise InvalidAllocationInput(
                "INVALID_LIQUIDITY_EVIDENCE", "liquidity observed_at must be timezone-aware"
            )
        if self.max_age <= timedelta(0):
            raise InvalidAllocationInput(
                "INVALID_LIQUIDITY_EVIDENCE", "liquidity max age must be positive"
            )
        if self.security_status not in {"active", "suspended", "delisted", "unknown"}:
            raise InvalidAllocationInput(
                "INVALID_LIQUIDITY_EVIDENCE", "liquidity security status is invalid"
            )
        if not 1 <= len(self.observations) <= 20:
            raise InvalidAllocationInput(
                "INVALID_LIQUIDITY_EVIDENCE", "liquidity requires one to twenty sessions"
            )
        dates = [item.session_date for item in self.observations]
        if len(set(dates)) != len(dates):
            raise InvalidAllocationInput(
                "INVALID_LIQUIDITY_EVIDENCE", "liquidity sessions must be distinct"
            )
        if not self.source_url.startswith("https://iss.moex.com/"):
            raise InvalidAllocationInput(
                "INVALID_LIQUIDITY_EVIDENCE", "liquidity source must be allowlisted MOEX HTTPS"
            )

    def is_fresh_at(self, calculated_at: datetime) -> bool:
        if calculated_at.tzinfo is None or calculated_at.utcoffset() is None:
            return False
        age = calculated_at - self.observed_at
        return timedelta(0) <= age <= self.max_age


@dataclass(frozen=True, slots=True)
class MarketCandidate:
    asset_id: str
    name: str
    kind: InstrumentKind
    currency: str
    lot_size: int
    unit_price: Decimal
    price_as_of: datetime
    max_age: timedelta
    source_url: str
    classification_url: str
    quote_kind: str
    turnover: Decimal
    maturity_date: date | None = None
    yield_percent: Decimal | None = None
    clean_price_percent: Decimal | None = None
    face_value: Decimal | None = None
    accrued_interest: Decimal | None = None
    next_coupon_date: date | None = None
    coupon_percent: Decimal | None = None
    coupon_value: Decimal | None = None
    research: DividendResearchEvidence | None = None
    liquidity: MarketLiquidityEvidence | None = None

    def __post_init__(self) -> None:
        if not self.asset_id.strip() or not self.name.strip():
            raise InvalidAllocationInput(
                "INVALID_MARKET_CANDIDATE", "asset id and name are required"
            )
        if not self.source_url.startswith("https://") or not self.classification_url.startswith(
            "https://"
        ):
            raise InvalidAllocationInput(
                "INVALID_MARKET_CANDIDATE", "market evidence must use HTTPS"
            )
        if not self.quote_kind.strip():
            raise InvalidAllocationInput("INVALID_MARKET_CANDIDATE", "quote kind is required")
        validate_currency(self.currency)
        if (
            isinstance(self.lot_size, bool)
            or not isinstance(self.lot_size, int)
            or self.lot_size <= 0
        ):
            raise InvalidAllocationInput("INVALID_MARKET_CANDIDATE", "lot size must be positive")
        _finite(self.unit_price, name="unit price", positive=True)
        _finite(self.turnover, name="turnover")
        if self.turnover < 0:
            raise InvalidAllocationInput("INVALID_MARKET_CANDIDATE", "turnover cannot be negative")
        if self.price_as_of.tzinfo is None or self.price_as_of.utcoffset() is None:
            raise InvalidAllocationInput(
                "INVALID_MARKET_CANDIDATE", "price timestamp must be timezone-aware"
            )
        if self.max_age <= timedelta(0):
            raise InvalidAllocationInput("INVALID_MARKET_CANDIDATE", "max age must be positive")
        optional_decimals = (
            ("yield", self.yield_percent),
            ("clean price", self.clean_price_percent),
            ("face value", self.face_value),
            ("accrued interest", self.accrued_interest),
            ("coupon percent", self.coupon_percent),
            ("coupon value", self.coupon_value),
        )
        for name, value in optional_decimals:
            if value is not None:
                _finite(value, name=name)
        if self.kind is InstrumentKind.OFZ and (
            self.maturity_date is None
            or self.clean_price_percent is None
            or self.face_value is None
            or self.accrued_interest is None
        ):
            raise InvalidAllocationInput(
                "INVALID_MARKET_CANDIDATE", "OFZ requires maturity and dirty-price components"
            )
        if self.kind is InstrumentKind.DIVIDEND_STOCK and self.research is None:
            raise InvalidAllocationInput(
                "INVALID_MARKET_CANDIDATE",
                "dividend stock requires typed research evidence",
            )
        if (
            self.kind not in {InstrumentKind.DIVIDEND_STOCK, InstrumentKind.PUBLIC_EQUITY}
            and self.research is not None
        ):
            raise InvalidAllocationInput(
                "INVALID_MARKET_CANDIDATE",
                "dividend research evidence belongs only to dividend stocks",
            )

    @property
    def lot_cost(self) -> Decimal:
        return self.unit_price * self.lot_size


@dataclass(frozen=True, slots=True)
class MarketScan:
    policy_version: str
    observed_at: datetime
    candidates: tuple[MarketCandidate, ...]
    universe_size: int
    kind_counts: dict[str, int]
    enriched_count: int

    def __post_init__(self) -> None:
        if not self.policy_version.strip():
            raise InvalidAllocationInput("INVALID_MARKET_SCAN", "scan policy version is required")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise InvalidAllocationInput("INVALID_MARKET_SCAN", "scan time must be timezone-aware")
        if self.universe_size < len(self.candidates) or self.enriched_count < 0:
            raise InvalidAllocationInput("INVALID_MARKET_SCAN", "scan coverage counts are invalid")
        if any(value < 0 for value in self.kind_counts.values()):
            raise InvalidAllocationInput("INVALID_MARKET_SCAN", "scan kind counts are invalid")


class MarketDataProvider(Protocol):
    name: str

    def discover(self, *, calculated_at: datetime) -> tuple[MarketCandidate, ...]: ...


@runtime_checkable
class MarketScanProvider(MarketDataProvider, Protocol):
    def scan(self, *, calculated_at: datetime) -> MarketScan: ...
