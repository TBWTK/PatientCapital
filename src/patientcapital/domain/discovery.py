"""Versioned, deterministic selection of source-backed market candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from patientcapital.domain.errors import InvalidAllocationInput
from patientcapital.marketdata.models import InstrumentKind, MarketCandidate
from patientcapital.research.models import BalanceSheetStatus, CorporateActionStatus

DISCOVERY_POLICY_VERSION = "five-year-moex-v2"
DIVIDEND_POLICY_VERSION = "dividend-quality-v1"
_CORE_WEIGHTS: dict[str, tuple[Decimal, Decimal]] = {
    "conservative": (Decimal("0.80000000"), Decimal("0.20000000")),
    "balanced": (Decimal("0.60000000"), Decimal("0.40000000")),
    "growth": (Decimal("0.40000000"), Decimal("0.60000000")),
}
_EXPANDED_WEIGHTS: dict[str, tuple[Decimal, Decimal, Decimal]] = {
    "growth": (Decimal("0.40000000"), Decimal("0.40000000"), Decimal("0.20000000")),
}
_MATURITY_WINDOW_DAYS = 366
_MIN_DIVIDEND_STOCK_TURNOVER = Decimal("10000000")


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


def _dividend_rejection_reason(
    candidate: MarketCandidate,
    *,
    contribution: Decimal,
    risk_level: str,
    calculated_at: datetime,
) -> str | None:
    if risk_level != "growth":
        return "Dividend-stock category в MVP допускается только риск-профилем «рост»."
    research = candidate.research
    if research is None or research.policy_version != DIVIDEND_POLICY_VERSION:
        return "Отсутствует evidence допустимой версии dividend research policy."
    if not research.is_fresh_at(calculated_at):
        return "Research evidence просрочено или имеет недопустимое время наблюдения."
    if research.profitable_years < 3:
        return "Недостаточно подтверждённых прибыльных отчётных периодов."
    if research.dividend_years < 3:
        return "Недостаточно подтверждённой дивидендной истории."
    if research.payout_ratio_percent <= 0 or research.payout_ratio_percent > 100:
        return "Дивиденд не покрыт подтверждённой прибылью."
    if research.balance_sheet_status not in {
        BalanceSheetStatus.NO_DEBT,
        BalanceSheetStatus.ADEQUATE_CAPITAL,
    }:
        return "Состояние баланса неизвестно или содержит подтверждённый риск."
    if not research.governance_program_member:
        return "Отдельная проверка корпоративного управления не пройдена."
    if (
        research.corporate_action_status
        is not CorporateActionStatus.NO_MATERIAL_ACTION_IDENTIFIED
    ):
        return "Выявлено или не исключено существенное корпоративное действие."
    if candidate.turnover < _MIN_DIVIDEND_STOCK_TURNOVER:
        return "Недостаточная подтверждённая ликвидность dividend-stock кандидата."
    if candidate.currency != "RUB":
        return "Валюта инструмента не соответствует рублёвой policy."
    if candidate.lot_cost > contribution:
        return "Стоимость целого лота превышает сумму пополнения."
    return None


def _select_dividend_stock(
    candidates: tuple[MarketCandidate, ...],
    *,
    contribution: Decimal,
    risk_level: str,
    calculated_at: datetime,
) -> MarketCandidate | None:
    eligible = [
        item
        for item in candidates
        if item.kind is InstrumentKind.DIVIDEND_STOCK
        and _dividend_rejection_reason(
            item,
            contribution=contribution,
            risk_level=risk_level,
            calculated_at=calculated_at,
        )
        is None
    ]
    if not eligible:
        return None
    return min(eligible, key=lambda item: (-item.turnover, item.asset_id))


def _normalized_weights(
    selected: tuple[tuple[MarketCandidate | None, Decimal], ...]
) -> dict[str, Decimal]:
    available = [(candidate, weight) for candidate, weight in selected if candidate is not None]
    total = sum((weight for _, weight in available), Decimal("0"))
    result: dict[str, Decimal] = {}
    allocated = Decimal("0")
    for index, (candidate, weight) in enumerate(available):
        if index == len(available) - 1:
            normalized = Decimal("1.00000000") - allocated
        else:
            normalized = (weight / total).quantize(Decimal("0.00000001"))
            allocated += normalized
        result[candidate.asset_id] = normalized
    return result


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
    if risk_level not in _CORE_WEIGHTS:
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
    stock = _select_dividend_stock(
        candidates,
        contribution=contribution,
        risk_level=risk_level,
        calculated_at=calculated_at,
    )
    if ofz is None and fund is None and stock is None:
        raise InvalidAllocationInput(
            "NO_AFFORDABLE_MARKET_CANDIDATE",
            "no validated MOEX lot fits the contribution",
        )

    if stock is None:
        bond_weight, fund_weight = _CORE_WEIGHTS[risk_level]
        weights = _normalized_weights(((ofz, bond_weight), (fund, fund_weight)))
    else:
        bond_weight, fund_weight, stock_weight = _EXPANDED_WEIGHTS[risk_level]
        weights = _normalized_weights(
            ((ofz, bond_weight), (fund, fund_weight), (stock, stock_weight))
        )
    selected: list[SelectedCandidate] = []
    if ofz is not None:
        maturity = ofz.maturity_date
        if maturity is None:  # guarded by the OFZ candidate contract
            raise InvalidAllocationInput("INVALID_MARKET_CANDIDATE", "selected OFZ has no maturity")
        selected.append(
            SelectedCandidate(
                ofz,
                weights[ofz.asset_id],
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
                weights[fund.asset_id],
                "Самый ликвидный доступный фонд широкого индекса из source-backed реестра MOEX.",
            )
        )
    if stock is not None:
        selected.append(
            SelectedCandidate(
                stock,
                weights[stock.asset_id],
                (
                    "Ликвидная дивидендная акция прошла отдельные fundamental, payout, "
                    "governance и corporate-action gates; dividend capture не используется."
                ),
            )
        )
    selected_ids = {item.candidate.asset_id for item in selected}
    rejected: list[RejectedCandidate] = []
    for candidate in candidates:
        if candidate.asset_id in selected_ids:
            continue
        if candidate.kind is InstrumentKind.DIVIDEND_STOCK:
            reason = _dividend_rejection_reason(
                candidate,
                contribution=contribution,
                risk_level=risk_level,
                calculated_at=calculated_at,
            ) or "Акция уступила выбранному кандидату в dividend-quality ranking policy."
        elif candidate.currency != "RUB":
            reason = "Валюта инструмента не соответствует рублёвой policy."
        elif candidate.lot_cost > contribution:
            reason = "Стоимость целого лота превышает сумму пополнения."
        else:
            reason = "Инструмент уступил выбранному кандидату в детерминированном ranking policy."
        rejected.append(RejectedCandidate(candidate, reason))
    return MarketSelection(DISCOVERY_POLICY_VERSION, tuple(selected), tuple(rejected))
