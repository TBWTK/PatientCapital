"""Deterministic asset-admission policy; narrative cannot alter a verdict."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import cast

from patientcapital.marketdata.models import (
    InstrumentKind,
    LiquidityObservation,
    MarketCandidate,
    MarketLiquidityEvidence,
)
from patientcapital.research.models import BalanceSheetStatus, CorporateActionStatus, ResearchScope

ADMISSION_POLICY_VERSION = "asset-admission-v2"
LIQUIDITY_POLICY_VERSION = "market-liquidity-v2"
DIVIDEND_ADMISSION_POLICY_VERSION = "equity-dividend-quality-v1"
OFZ_ADMISSION_POLICY_VERSION = "ofz-admission-v1"
FUND_ADMISSION_POLICY_VERSION = "broad-index-fund-admission-v1"


class AdmissionStatus(StrEnum):
    ELIGIBLE = "eligible"
    WATCH = "watch"
    REJECT = "reject"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class AdmissionGate:
    gate_id: str
    status: AdmissionStatus
    reason_code: str
    observed_value: str | None
    unit: str | None
    threshold: str | None
    source_url: str
    observed_at: datetime
    valid_until: datetime
    material: bool = True


@dataclass(frozen=True, slots=True)
class AdmissionDimension:
    policy_version: str
    status: AdmissionStatus
    gates: tuple[AdmissionGate, ...]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssetAdmissionProfile:
    policy_version: str
    asset_id: str
    instrument_kind: InstrumentKind
    strategy_profile: str
    overall_status: AdmissionStatus
    evaluated_at: datetime
    expires_at: datetime
    liquidity: AdmissionDimension
    investment: AdmissionDimension
    reason_codes: tuple[str, ...]
    hard_kills: tuple[str, ...]
    unknowns: tuple[str, ...]


_STATUS_PRIORITY = {
    AdmissionStatus.ELIGIBLE: 0,
    AdmissionStatus.WATCH: 1,
    AdmissionStatus.UNKNOWN: 2,
    AdmissionStatus.REJECT: 3,
}


def compose_statuses(statuses: tuple[AdmissionStatus, ...]) -> AdmissionStatus:
    if not statuses:
        return AdmissionStatus.UNKNOWN
    return max(statuses, key=_STATUS_PRIORITY.__getitem__)


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / Decimal("2")


def _gate(
    gate_id: str,
    status: AdmissionStatus,
    reason_code: str,
    *,
    evidence: MarketLiquidityEvidence,
    observed_value: str | None = None,
    unit: str | None = None,
    threshold: str | None = None,
    material: bool = True,
) -> AdmissionGate:
    return AdmissionGate(
        gate_id=gate_id,
        status=status,
        reason_code=reason_code,
        observed_value=observed_value,
        unit=unit,
        threshold=threshold,
        source_url=evidence.source_url,
        observed_at=evidence.observed_at,
        valid_until=evidence.observed_at + evidence.max_age,
        material=material,
    )


def _turnover_thresholds(kind: InstrumentKind) -> tuple[Decimal, Decimal]:
    if kind in {InstrumentKind.DIVIDEND_STOCK, InstrumentKind.PUBLIC_EQUITY}:
        return Decimal("50000000"), Decimal("10000000")
    if kind is InstrumentKind.OFZ:
        return Decimal("25000000"), Decimal("5000000")
    return Decimal("5000000"), Decimal("1000000")


def _spread_thresholds(kind: InstrumentKind) -> tuple[Decimal, Decimal]:
    if kind in {InstrumentKind.DIVIDEND_STOCK, InstrumentKind.PUBLIC_EQUITY}:
        return Decimal("0.75"), Decimal("1.50")
    return Decimal("0.50"), Decimal("1.00")


def evaluate_market_liquidity(
    kind: InstrumentKind,
    evidence: MarketLiquidityEvidence | None,
    *,
    calculated_at: datetime,
) -> AdmissionDimension:
    if evidence is None:
        return AdmissionDimension(
            policy_version=LIQUIDITY_POLICY_VERSION,
            status=AdmissionStatus.UNKNOWN,
            gates=(),
            reason_codes=("LIQUIDITY_EVIDENCE_MISSING",),
        )
    gates: list[AdmissionGate] = []
    if evidence.policy_version != LIQUIDITY_POLICY_VERSION:
        return AdmissionDimension(
            policy_version=LIQUIDITY_POLICY_VERSION,
            status=AdmissionStatus.UNKNOWN,
            gates=(),
            reason_codes=("LIQUIDITY_POLICY_UNSUPPORTED",),
        )

    status_map = {
        "active": (AdmissionStatus.ELIGIBLE, "LIQUIDITY_SECURITY_ACTIVE"),
        "suspended": (AdmissionStatus.REJECT, "LIQUIDITY_SECURITY_SUSPENDED"),
        "delisted": (AdmissionStatus.REJECT, "LIQUIDITY_SECURITY_DELISTED"),
        "unknown": (AdmissionStatus.UNKNOWN, "LIQUIDITY_SECURITY_STATUS_UNKNOWN"),
    }
    security_status, security_reason = status_map[evidence.security_status]
    gates.append(
        _gate(
            "security_status",
            security_status,
            security_reason,
            evidence=evidence,
            observed_value=evidence.security_status,
            threshold="active",
        )
    )

    sessions = len(evidence.observations)
    window_status = AdmissionStatus.ELIGIBLE if sessions == 20 else AdmissionStatus.UNKNOWN
    gates.append(
        _gate(
            "observation_window",
            window_status,
            "LIQUIDITY_WINDOW_COMPLETE" if sessions == 20 else "LIQUIDITY_WINDOW_INCOMPLETE",
            evidence=evidence,
            observed_value=str(sessions),
            unit="sessions",
            threshold="=20",
        )
    )

    traded_sessions = sum(item.trades > 0 for item in evidence.observations)
    if sessions < 20:
        coverage_status = AdmissionStatus.UNKNOWN
        coverage_reason = "LIQUIDITY_TRADE_COVERAGE_UNKNOWN"
    elif traded_sessions >= 18:
        coverage_status = AdmissionStatus.ELIGIBLE
        coverage_reason = "LIQUIDITY_TRADE_COVERAGE_PASS"
    elif traded_sessions >= 15:
        coverage_status = AdmissionStatus.WATCH
        coverage_reason = "LIQUIDITY_TRADE_COVERAGE_WATCH"
    else:
        coverage_status = AdmissionStatus.REJECT
        coverage_reason = "LIQUIDITY_TRADE_COVERAGE_REJECT"
    gates.append(
        _gate(
            "trade_coverage",
            coverage_status,
            coverage_reason,
            evidence=evidence,
            observed_value=str(traded_sessions),
            unit="sessions",
            threshold=">=18 eligible; >=15 watch",
        )
    )

    median_turnover = _median([item.turnover_rub for item in evidence.observations])
    turnover_pass, turnover_watch = _turnover_thresholds(kind)
    if median_turnover >= turnover_pass:
        turnover_status = AdmissionStatus.ELIGIBLE
        turnover_reason = "LIQUIDITY_TURNOVER_PASS"
    elif median_turnover >= turnover_watch:
        turnover_status = AdmissionStatus.WATCH
        turnover_reason = "LIQUIDITY_TURNOVER_WATCH"
    else:
        turnover_status = AdmissionStatus.REJECT
        turnover_reason = "LIQUIDITY_TURNOVER_REJECT"
    gates.append(
        _gate(
            "median_turnover",
            turnover_status,
            turnover_reason,
            evidence=evidence,
            observed_value=str(median_turnover),
            unit="RUB",
            threshold=f">={turnover_pass} eligible; >={turnover_watch} watch",
        )
    )

    spreads = [
        value for item in evidence.observations if (value := item.spread_percent) is not None
    ]
    spread_pass, spread_watch = _spread_thresholds(kind)
    if not spreads:
        spread_status = AdmissionStatus.UNKNOWN
        spread_reason = "LIQUIDITY_SPREAD_UNKNOWN"
        spread_value = None
    else:
        spread_value_decimal = _median(spreads)
        spread_value = str(spread_value_decimal)
        if spread_value_decimal <= spread_pass:
            spread_status = AdmissionStatus.ELIGIBLE
            spread_reason = "LIQUIDITY_SPREAD_PASS"
        elif spread_value_decimal <= spread_watch:
            spread_status = AdmissionStatus.WATCH
            spread_reason = "LIQUIDITY_SPREAD_WATCH"
        else:
            spread_status = AdmissionStatus.REJECT
            spread_reason = "LIQUIDITY_SPREAD_REJECT"
    gates.append(
        _gate(
            "median_spread",
            spread_status,
            spread_reason,
            evidence=evidence,
            observed_value=spread_value,
            unit="percent",
            threshold=(f"<={spread_pass} eligible; <={spread_watch} watch; samples={len(spreads)}"),
            material=bool(spreads),
        )
    )

    evidence_freshness_status = (
        AdmissionStatus.ELIGIBLE if evidence.is_fresh_at(calculated_at) else AdmissionStatus.UNKNOWN
    )
    gates.append(
        _gate(
            "evidence_freshness",
            evidence_freshness_status,
            "LIQUIDITY_FRESH"
            if evidence_freshness_status is AdmissionStatus.ELIGIBLE
            else "LIQUIDITY_STALE",
            evidence=evidence,
            observed_value=evidence.observed_at.isoformat(),
            unit="datetime",
            threshold=f"age<={int(evidence.max_age.total_seconds())}s",
        )
    )
    latest_session = max(item.session_date for item in evidence.observations)
    session_age = calculated_at.date() - latest_session
    max_session_age_days = max(1, int(evidence.max_age.total_seconds() // 86_400))
    session_freshness_status = (
        AdmissionStatus.ELIGIBLE
        if timedelta(0) <= session_age <= timedelta(days=max_session_age_days)
        else AdmissionStatus.UNKNOWN
    )
    gates.append(
        _gate(
            "last_completed_session",
            session_freshness_status,
            "LIQUIDITY_LAST_SESSION_FRESH"
            if session_freshness_status is AdmissionStatus.ELIGIBLE
            else "LIQUIDITY_LAST_SESSION_STALE",
            evidence=evidence,
            observed_value=latest_session.isoformat(),
            unit="date",
            threshold=f"age<={max_session_age_days}d",
        )
    )
    status = compose_statuses(tuple(item.status for item in gates if item.material))
    return AdmissionDimension(
        policy_version=LIQUIDITY_POLICY_VERSION,
        status=status,
        gates=tuple(gates),
        reason_codes=tuple(
            item.reason_code for item in gates if item.status is not AdmissionStatus.ELIGIBLE
        ),
    )


def _investment_dimension(
    candidate: MarketCandidate, *, calculated_at: datetime
) -> tuple[AdmissionDimension, tuple[str, ...], tuple[str, ...]]:
    source = candidate.source_url
    valid_until = candidate.price_as_of + candidate.max_age

    def result(
        policy: str,
        status: AdmissionStatus,
        reason: str,
    ) -> tuple[AdmissionDimension, tuple[str, ...], tuple[str, ...]]:
        gate = AdmissionGate(
            gate_id="investment_admission",
            status=status,
            reason_code=reason,
            observed_value=status.value,
            unit="status",
            threshold=None,
            source_url=source,
            observed_at=candidate.price_as_of,
            valid_until=valid_until,
        )
        hard_kills = (reason,) if status is AdmissionStatus.REJECT else ()
        unknowns = (reason,) if status is AdmissionStatus.UNKNOWN else ()
        return AdmissionDimension(policy, status, (gate,), (reason,)), hard_kills, unknowns

    if candidate.kind is InstrumentKind.OFZ:
        if (
            candidate.maturity_date is None
            or candidate.maturity_date <= calculated_at.date()
            or candidate.yield_percent is None
        ):
            return result(
                OFZ_ADMISSION_POLICY_VERSION, AdmissionStatus.UNKNOWN, "OFZ_TERMS_UNKNOWN"
            )
        return result(OFZ_ADMISSION_POLICY_VERSION, AdmissionStatus.ELIGIBLE, "OFZ_TERMS_VALID")
    if candidate.kind is InstrumentKind.EQUITY_INDEX_FUND:
        if candidate.classification_url != "https://www.moex.com/msn/etf":
            return result(
                FUND_ADMISSION_POLICY_VERSION,
                AdmissionStatus.UNKNOWN,
                "FUND_CLASSIFICATION_UNKNOWN",
            )
        return result(
            FUND_ADMISSION_POLICY_VERSION, AdmissionStatus.ELIGIBLE, "FUND_CLASSIFICATION_VALID"
        )

    research = candidate.research
    if research is None or research.scope is ResearchScope.MARKET_SCREEN:
        return result(
            DIVIDEND_ADMISSION_POLICY_VERSION,
            AdmissionStatus.UNKNOWN,
            "ADMISSION_RESEARCH_ONLY",
        )
    if research.policy_version != "dividend-quality-v1" or not research.is_fresh_at(calculated_at):
        return result(
            DIVIDEND_ADMISSION_POLICY_VERSION,
            AdmissionStatus.UNKNOWN,
            "ADMISSION_RESEARCH_STALE_OR_UNSUPPORTED",
        )
    if research.corporate_action_status is CorporateActionStatus.MATERIAL:
        return result(
            DIVIDEND_ADMISSION_POLICY_VERSION,
            AdmissionStatus.REJECT,
            "DIVIDEND_MATERIAL_CORPORATE_ACTION",
        )
    if research.corporate_action_status is CorporateActionStatus.UNKNOWN:
        return result(
            DIVIDEND_ADMISSION_POLICY_VERSION,
            AdmissionStatus.UNKNOWN,
            "DIVIDEND_CORPORATE_ACTION_UNKNOWN",
        )
    if research.last_registry_close_date is None or (
        calculated_at.date() - research.last_registry_close_date
    ) > timedelta(days=730):
        return result(
            DIVIDEND_ADMISSION_POLICY_VERSION,
            AdmissionStatus.UNKNOWN,
            "DIVIDEND_FACT_STALE",
        )
    profitable_years = cast(int, research.profitable_years)
    payout_ratio_percent = cast(Decimal, research.payout_ratio_percent)
    governance_program_member = cast(bool, research.governance_program_member)
    if profitable_years < 3:
        return result(
            DIVIDEND_ADMISSION_POLICY_VERSION, AdmissionStatus.REJECT, "DIVIDEND_PROFITABILITY_FAIL"
        )
    if research.dividend_years < 3:
        return result(
            DIVIDEND_ADMISSION_POLICY_VERSION, AdmissionStatus.REJECT, "DIVIDEND_CONTINUITY_FAIL"
        )
    if not Decimal("0") < payout_ratio_percent <= Decimal("100"):
        return result(
            DIVIDEND_ADMISSION_POLICY_VERSION, AdmissionStatus.REJECT, "DIVIDEND_PAYOUT_FAIL"
        )
    if research.balance_sheet_status is BalanceSheetStatus.CONCERN:
        return result(
            DIVIDEND_ADMISSION_POLICY_VERSION, AdmissionStatus.REJECT, "DIVIDEND_BALANCE_FAIL"
        )
    if research.balance_sheet_status is BalanceSheetStatus.UNKNOWN:
        return result(
            DIVIDEND_ADMISSION_POLICY_VERSION, AdmissionStatus.UNKNOWN, "DIVIDEND_BALANCE_UNKNOWN"
        )
    if governance_program_member is False:
        return result(
            DIVIDEND_ADMISSION_POLICY_VERSION, AdmissionStatus.REJECT, "DIVIDEND_GOVERNANCE_FAIL"
        )
    return result(
        DIVIDEND_ADMISSION_POLICY_VERSION, AdmissionStatus.ELIGIBLE, "DIVIDEND_QUALITY_PASS"
    )


def evaluate_asset_admission(
    candidate: MarketCandidate, *, calculated_at: datetime
) -> AssetAdmissionProfile:
    liquidity = evaluate_market_liquidity(
        candidate.kind, candidate.liquidity, calculated_at=calculated_at
    )
    investment, hard_kills, unknowns = _investment_dimension(candidate, calculated_at=calculated_at)
    overall = compose_statuses((liquidity.status, investment.status))
    expiry_candidates = [candidate.price_as_of + candidate.max_age]
    if candidate.liquidity is not None:
        expiry_candidates.append(candidate.liquidity.observed_at + candidate.liquidity.max_age)
    if candidate.research is not None:
        expiry_candidates.append(candidate.research.observed_at + candidate.research.max_age)
    reason_codes = tuple(dict.fromkeys((*liquidity.reason_codes, *investment.reason_codes)))
    strategy = {
        InstrumentKind.OFZ: "sovereign_fixed_income",
        InstrumentKind.EQUITY_INDEX_FUND: "broad_index",
        InstrumentKind.DIVIDEND_STOCK: "dividend_quality",
        InstrumentKind.PUBLIC_EQUITY: "dividend_quality",
    }[candidate.kind]
    return AssetAdmissionProfile(
        policy_version=ADMISSION_POLICY_VERSION,
        asset_id=candidate.asset_id,
        instrument_kind=candidate.kind,
        strategy_profile=strategy,
        overall_status=overall,
        evaluated_at=calculated_at,
        expires_at=min(expiry_candidates),
        liquidity=liquidity,
        investment=investment,
        reason_codes=reason_codes,
        hard_kills=hard_kills,
        unknowns=unknowns,
    )


__all__ = [
    "ADMISSION_POLICY_VERSION",
    "LIQUIDITY_POLICY_VERSION",
    "AdmissionDimension",
    "AdmissionGate",
    "AdmissionStatus",
    "AssetAdmissionProfile",
    "LiquidityObservation",
    "MarketLiquidityEvidence",
    "compose_statuses",
    "evaluate_asset_admission",
    "evaluate_market_liquidity",
]
