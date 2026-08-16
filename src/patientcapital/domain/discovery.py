"""Versioned, deterministic selection of source-backed market candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from patientcapital.domain.errors import InvalidAllocationInput
from patientcapital.marketdata.models import InstrumentKind, MarketCandidate

DISCOVERY_POLICY_VERSION = "five-year-moex-v1"
_WEIGHTS: dict[str, tuple[Decimal, Decimal]] = {
    "conservative": (Decimal("0.80000000"), Decimal("0.20000000")),
    "balanced": (Decimal("0.60000000"), Decimal("0.40000000")),
    "growth": (Decimal("0.40000000"), Decimal("0.60000000")),
}
_MATURITY_WINDOW_DAYS = 366


@dataclass(frozen=True, slots=True)
class SelectedCandidate:
    candidate: MarketCandidate
    target_weight: Decimal
    rationale: str


@dataclass(frozen=True, slots=True)
class RejectedCandidate:
    candidate: MarketCandidate
    reason: str


@dataclass(frozen=True, slots=True)
class MarketSelection:
    policy_version: str
    items: tuple[SelectedCandidate, ...]
    rejected: tuple[RejectedCandidate, ...]


def _anniversary(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def _select_ofz(
    candidates: tuple[MarketCandidate, ...], *, contribution: Decimal, target_date: date
) -> MarketCandidate | None:
    eligible = [
        item
        for item in candidates
        if item.kind is InstrumentKind.OFZ
        and item.currency == "RUB"
        and item.maturity_date is not None
        and item.maturity_date > target_date.replace(year=target_date.year - 5)
        and item.lot_cost <= contribution
    ]
    if not eligible:
        return None
    near = [
        item
        for item in eligible
        if abs((item.maturity_date - target_date).days) <= _MATURITY_WINDOW_DAYS  # type: ignore[operator]
    ]
    pool = near or eligible
    return min(
        pool,
        key=lambda item: (
            -item.turnover,
            abs((item.maturity_date - target_date).days),  # type: ignore[operator]
            item.asset_id,
        ),
    )


def _select_fund(
    candidates: tuple[MarketCandidate, ...], *, contribution: Decimal
) -> MarketCandidate | None:
    eligible = [
        item
        for item in candidates
        if item.kind is InstrumentKind.EQUITY_INDEX_FUND
        and item.currency == "RUB"
        and item.lot_cost <= contribution
    ]
    if not eligible:
        return None
    return min(eligible, key=lambda item: (-item.turnover, item.asset_id))


def select_market_candidates(
    candidates: tuple[MarketCandidate, ...],
    *,
    contribution: Decimal,
    horizon_years: int,
    risk_level: str,
    calculated_at: datetime,
) -> MarketSelection:
    """Select an affordable OFZ/fund pair without model-owned facts or weights."""

    if horizon_years != 5:
        raise InvalidAllocationInput(
            "UNSUPPORTED_DISCOVERY_HORIZON",
            "automatic discovery policy supports exactly a five-year horizon",
        )
    if risk_level not in _WEIGHTS:
        raise InvalidAllocationInput(
            "UNSUPPORTED_RISK_LEVEL", f"unsupported risk level {risk_level}"
        )
    if not contribution.is_finite() or contribution <= 0:
        raise InvalidAllocationInput(
            "INVALID_DISCOVERY_CONTRIBUTION", "contribution must be positive"
        )
    if calculated_at.tzinfo is None or calculated_at.utcoffset() is None:
        raise InvalidAllocationInput(
            "INVALID_CALCULATION_TIME", "calculated_at must be timezone-aware"
        )

    target_date = _anniversary(calculated_at.date(), horizon_years)
    ofz = _select_ofz(candidates, contribution=contribution, target_date=target_date)
    fund = _select_fund(candidates, contribution=contribution)
    if ofz is None and fund is None:
        raise InvalidAllocationInput(
            "NO_AFFORDABLE_MARKET_CANDIDATE",
            "no validated MOEX lot fits the contribution",
        )

    bond_weight, fund_weight = _WEIGHTS[risk_level]
    selected: list[SelectedCandidate] = []
    if ofz is not None:
        maturity = ofz.maturity_date
        if maturity is None:  # guarded by the OFZ candidate contract
            raise InvalidAllocationInput("INVALID_MARKET_CANDIDATE", "selected OFZ has no maturity")
        selected.append(
            SelectedCandidate(
                ofz,
                bond_weight if fund is not None else Decimal("1.00000000"),
                (
                    "Ликвидный рублёвый выпуск ОФЗ в окне около пятилетней даты; "
                    f"погашение {maturity.isoformat()}."
                ),
            )
        )
    if fund is not None:
        selected.append(
            SelectedCandidate(
                fund,
                fund_weight if ofz is not None else Decimal("1.00000000"),
                "Самый ликвидный доступный фонд широкого индекса из source-backed реестра MOEX.",
            )
        )
    selected_ids = {item.candidate.asset_id for item in selected}
    rejected: list[RejectedCandidate] = []
    for candidate in candidates:
        if candidate.asset_id in selected_ids:
            continue
        if candidate.currency != "RUB":
            reason = "Валюта инструмента не соответствует рублёвой policy."
        elif candidate.lot_cost > contribution:
            reason = "Стоимость целого лота превышает сумму пополнения."
        else:
            reason = "Инструмент уступил выбранному кандидату в детерминированном ranking policy."
        rejected.append(RejectedCandidate(candidate, reason))
    return MarketSelection(DISCOVERY_POLICY_VERSION, tuple(selected), tuple(rejected))
