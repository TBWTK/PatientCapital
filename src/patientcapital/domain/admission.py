"""Deterministic asset-admission policy; narrative cannot alter a verdict."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from patientcapital.marketdata.models import (
    InstrumentKind,
    LiquidityObservation,
    MarketCandidate,
    MarketLiquidityEvidence,
)
from patientcapital.research.models import (
    IssuerAuditStatus,
    IssuerDecisionAuthority,
    IssuerEventKind,
    IssuerGovernanceStatus,
    IssuerSourceRole,
)

ADMISSION_POLICY_VERSION = "asset-admission-v3"
LIQUIDITY_POLICY_VERSION = "market-liquidity-v2"
DIVIDEND_ADMISSION_POLICY_VERSION = "equity-dividend-quality-v2"
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

    return _equity_investment_dimension(candidate, calculated_at=calculated_at)


def _equity_investment_dimension(
    candidate: MarketCandidate, *, calculated_at: datetime
) -> tuple[AdmissionDimension, tuple[str, ...], tuple[str, ...]]:
    evidence = candidate.issuer_evidence
    if evidence is None:
        gate = AdmissionGate(
            gate_id="issuer_evidence",
            status=AdmissionStatus.UNKNOWN,
            reason_code="EQDV2_EVIDENCE_MISSING",
            observed_value=None,
            unit=None,
            threshold="issuer-evidence-v2",
            source_url=candidate.source_url,
            observed_at=candidate.price_as_of,
            valid_until=candidate.price_as_of + candidate.max_age,
        )
        return (
            AdmissionDimension(
                DIVIDEND_ADMISSION_POLICY_VERSION,
                AdmissionStatus.UNKNOWN,
                (gate,),
                (gate.reason_code,),
            ),
            (),
            (gate.reason_code,),
        )

    documents_by_role = {
        role: next(item for item in evidence.documents if item.role is role)
        for role in IssuerSourceRole
        if any(item.role is role for item in evidence.documents)
    }

    def issuer_gate(
        gate_id: str,
        status: AdmissionStatus,
        reason_code: str,
        *,
        role: IssuerSourceRole,
        observed_value: str | None,
        threshold: str | None,
        unit: str | None = None,
    ) -> AdmissionGate:
        document = documents_by_role[role]
        return AdmissionGate(
            gate_id=gate_id,
            status=status,
            reason_code=reason_code,
            observed_value=observed_value,
            unit=unit,
            threshold=threshold,
            source_url=document.url,
            observed_at=evidence.observed_at,
            valid_until=evidence.valid_until,
        )

    gates: list[AdmissionGate] = []
    identity_ok = (
        candidate.isin is not None
        and candidate.asset_id == evidence.asset_id
        and candidate.isin == evidence.isin
    )
    gates.append(
        issuer_gate(
            "identity_source",
            AdmissionStatus.ELIGIBLE if identity_ok else AdmissionStatus.UNKNOWN,
            "EQDV2_IDENTITY_PASS" if identity_ok else "EQDV2_IDENTITY_MISMATCH",
            role=IssuerSourceRole.IDENTITY,
            observed_value=f"{evidence.asset_id}:{evidence.isin}",
            threshold=f"{candidate.asset_id}:{candidate.isin}",
        )
    )

    if evidence.conflicts:
        gates.append(
            issuer_gate(
                "fact_conflicts",
                AdmissionStatus.UNKNOWN,
                "EQDV2_FACT_CONFLICT",
                role=IssuerSourceRole.CORPORATE_ACTIONS,
                observed_value=",".join(item.conflict_id for item in evidence.conflicts),
                threshold="none",
            )
        )
    else:
        gates.append(
            issuer_gate(
                "fact_conflicts",
                AdmissionStatus.ELIGIBLE,
                "EQDV2_FACTS_CONSISTENT",
                role=IssuerSourceRole.CORPORATE_ACTIONS,
                observed_value="0",
                threshold="=0",
            )
        )

    reporting_period = evidence.research.reporting_period_end
    reporting_age = (
        (calculated_at.date() - reporting_period).days if reporting_period is not None else None
    )
    reporting_ok = (
        evidence.is_fresh_at(calculated_at)
        and reporting_age is not None
        and 0 <= reporting_age <= 210
    )
    gates.append(
        issuer_gate(
            "reporting_completeness",
            AdmissionStatus.ELIGIBLE if reporting_ok else AdmissionStatus.UNKNOWN,
            "EQDV2_REPORTING_PASS" if reporting_ok else "EQDV2_FINANCIALS_STALE_PERIOD",
            role=IssuerSourceRole.FINANCIALS,
            observed_value=reporting_period.isoformat() if reporting_period is not None else None,
            threshold="latest official period age <=210d",
            unit="date",
        )
    )

    audit_statuses = {
        IssuerAuditStatus.CLEAN: (AdmissionStatus.ELIGIBLE, "EQDV2_AUDIT_PASS"),
        IssuerAuditStatus.QUALIFIED: (
            AdmissionStatus.WATCH,
            "EQDV2_AUDIT_QUALIFIED_REVIEW",
        ),
        IssuerAuditStatus.GOING_CONCERN: (AdmissionStatus.REJECT, "EQDV2_GOING_CONCERN"),
        IssuerAuditStatus.ADVERSE: (AdmissionStatus.REJECT, "EQDV2_AUDIT_ADVERSE"),
        IssuerAuditStatus.UNKNOWN: (AdmissionStatus.UNKNOWN, "EQDV2_AUDIT_UNKNOWN"),
    }
    audit_status, audit_reason = audit_statuses[evidence.audit_status]
    gates.append(
        issuer_gate(
            "audit",
            audit_status,
            audit_reason,
            role=IssuerSourceRole.AUDIT,
            observed_value=evidence.audit_status.value,
            threshold="clean",
        )
    )

    profitable_years = evidence.research.profitable_years
    profitability_ok = evidence.latest_period_profitable is True and (
        profitable_years is not None and profitable_years >= 3
    )
    profitability_unknown = (
        evidence.latest_period_profitable is None or profitable_years is None
    )
    gates.append(
        issuer_gate(
            "profitability",
            (
                AdmissionStatus.UNKNOWN
                if profitability_unknown
                else AdmissionStatus.ELIGIBLE
                if profitability_ok
                else AdmissionStatus.REJECT
            ),
            (
                "EQDV2_PROFITABILITY_UNKNOWN"
                if profitability_unknown
                else "EQDV2_PROFITABILITY_PASS"
                if profitability_ok
                else "EQDV2_PROFITABILITY_FAIL"
            ),
            role=IssuerSourceRole.FINANCIALS,
            observed_value=(
                f"latest={evidence.latest_period_profitable};positive_years={profitable_years}"
            ),
            threshold="latest positive and >=3/4 positive FY",
        )
    )

    active_events = tuple(
        item
        for item in evidence.events
        if item.effective_from <= calculated_at.date()
        and (item.effective_until is None or calculated_at.date() <= item.effective_until)
    )
    hard_event_reason: str | None = None
    if any(
        item.authority is IssuerDecisionAuthority.BINDING
        and item.kind in {IssuerEventKind.DIVIDEND_SUSPENDED, IssuerEventKind.DIVIDEND_CANCELLED}
        for item in active_events
    ):
        hard_event_reason = "EQDV2_BINDING_DIVIDEND_SUSPENSION"
    elif any(item.kind is IssuerEventKind.DEFAULT_OR_INSOLVENCY for item in active_events):
        hard_event_reason = "EQDV2_DEFAULT_OR_INSOLVENCY"
    elif any(item.kind is IssuerEventKind.DELISTING for item in active_events):
        hard_event_reason = "EQDV2_BINDING_DELISTING"

    nonbinding_adverse = any(
        item.authority is IssuerDecisionAuthority.NON_BINDING
        and item.kind in {IssuerEventKind.DIVIDEND_SUSPENDED, IssuerEventKind.DIVIDEND_CANCELLED}
        for item in active_events
    )
    if hard_event_reason is not None:
        event_status = AdmissionStatus.REJECT
        event_reason = hard_event_reason
    elif nonbinding_adverse:
        event_status = AdmissionStatus.WATCH
        event_reason = "EQDV2_DIVIDEND_NONBINDING_ADVERSE"
    else:
        review_event = next(
            (
                item
                for item in active_events
                if item.kind
                in {
                    IssuerEventKind.DILUTION,
                    IssuerEventKind.RELATED_PARTY,
                    IssuerEventKind.GOVERNANCE_CHANGE,
                    IssuerEventKind.RESTRUCTURING,
                }
            ),
            None,
        )
        if review_event is None:
            event_status, event_reason = AdmissionStatus.ELIGIBLE, "EQDV2_EVENTS_CLEAR"
        else:
            event_status = AdmissionStatus.WATCH
            event_reason = {
                IssuerEventKind.DILUTION: "EQDV2_DILUTION_REVIEW",
                IssuerEventKind.RELATED_PARTY: "EQDV2_RELATED_PARTY_REVIEW",
                IssuerEventKind.GOVERNANCE_CHANGE: "EQDV2_GOVERNANCE_CHANGE_REVIEW",
                IssuerEventKind.RESTRUCTURING: "EQDV2_GOVERNANCE_CHANGE_REVIEW",
            }[review_event.kind]
    gates.append(
        issuer_gate(
            "material_events",
            event_status,
            event_reason,
            role=IssuerSourceRole.CORPORATE_ACTIONS,
            observed_value=",".join(item.kind.value for item in active_events) or "none",
            threshold="no active adverse binding event",
        )
    )

    coverage_age = calculated_at - evidence.event_coverage_through
    coverage_ok = timedelta(0) <= coverage_age <= timedelta(hours=8)
    gates.append(
        issuer_gate(
            "event_coverage_freshness",
            AdmissionStatus.ELIGIBLE if coverage_ok else AdmissionStatus.UNKNOWN,
            "EQDV2_EVENT_COVERAGE_PASS"
            if coverage_ok
            else "EQDV2_EVENT_COVERAGE_STALE",
            role=IssuerSourceRole.CORPORATE_ACTIONS,
            observed_value=evidence.event_coverage_through.isoformat(),
            threshold="age <=8h",
            unit="datetime",
        )
    )

    dividend_paid = any(item.kind is IssuerEventKind.DIVIDEND_PAID for item in active_events)
    continuity_ok = (
        evidence.research.dividend_years >= 3
        and evidence.research.last_registry_close_date is not None
        and dividend_paid
    )
    gates.append(
        issuer_gate(
            "dividend_continuity",
            AdmissionStatus.ELIGIBLE if continuity_ok else AdmissionStatus.UNKNOWN,
            "EQDV2_DIVIDEND_CONTINUITY_PASS"
            if continuity_ok
            else "EQDV2_DIVIDEND_DECISION_MISSING",
            role=IssuerSourceRole.DIVIDENDS,
            observed_value=(
                f"years={evidence.research.dividend_years};paid_event={dividend_paid}"
            ),
            threshold=">=3/4 due FY including latest due and payment evidence",
        )
    )

    payout = evidence.research.payout_ratio_percent
    payout_unknown = payout is None
    payout_ok = payout is not None and Decimal("0") < payout <= Decimal("100")
    gates.append(
        issuer_gate(
            "payout_coverage",
            (
                AdmissionStatus.UNKNOWN
                if payout_unknown
                else AdmissionStatus.ELIGIBLE
                if payout_ok
                else AdmissionStatus.REJECT
            ),
            (
                "EQDV2_PAYOUT_BASIS_MISMATCH"
                if payout_unknown
                else "EQDV2_PAYOUT_PASS"
                if payout_ok
                else "EQDV2_PAYOUT_UNCOVERED"
            ),
            role=IssuerSourceRole.DIVIDENDS,
            observed_value=str(payout) if payout is not None else None,
            threshold="0 < payout/profit <=100",
            unit="percent",
        )
    )

    gates.append(
        issuer_gate(
            "balance_minimum",
            (
                AdmissionStatus.UNKNOWN
                if evidence.positive_equity is None
                else AdmissionStatus.ELIGIBLE
                if evidence.positive_equity
                else AdmissionStatus.REJECT
            ),
            (
                "EQDV2_BALANCE_UNKNOWN"
                if evidence.positive_equity is None
                else "EQDV2_BALANCE_MINIMUM_PASS"
                if evidence.positive_equity
                else "EQDV2_NEGATIVE_EQUITY"
            ),
            role=IssuerSourceRole.FINANCIALS,
            observed_value=str(evidence.positive_equity),
            threshold="total equity >0",
        )
    )

    governance_statuses = {
        IssuerGovernanceStatus.CLEAR: (
            AdmissionStatus.ELIGIBLE,
            "EQDV2_GOVERNANCE_MINIMUM_PASS",
        ),
        IssuerGovernanceStatus.REVIEW: (
            AdmissionStatus.WATCH,
            "EQDV2_GOVERNANCE_CHANGE_REVIEW",
        ),
        IssuerGovernanceStatus.UNKNOWN: (
            AdmissionStatus.UNKNOWN,
            "EQDV2_GOVERNANCE_UNKNOWN",
        ),
    }
    governance_status, governance_reason = governance_statuses[evidence.governance_status]
    gates.append(
        issuer_gate(
            "governance_minimum",
            governance_status,
            governance_reason,
            role=IssuerSourceRole.GOVERNANCE,
            observed_value=evidence.governance_status.value,
            threshold="current filings and no active rights event",
        )
    )

    status = compose_statuses(tuple(item.status for item in gates))
    non_pass_reasons = tuple(
        item.reason_code for item in gates if item.status is not AdmissionStatus.ELIGIBLE
    )
    reason_codes = non_pass_reasons or ("EQDV2_ELIGIBLE",)
    hard_kills = tuple(
        item.reason_code
        for item in gates
        if item.reason_code
        in {
            "EQDV2_BINDING_DIVIDEND_SUSPENSION",
            "EQDV2_DEFAULT_OR_INSOLVENCY",
            "EQDV2_BINDING_DELISTING",
            "EQDV2_GOING_CONCERN",
            "EQDV2_AUDIT_ADVERSE",
        }
    )
    unknowns = tuple(
        item.reason_code for item in gates if item.status is AdmissionStatus.UNKNOWN
    )
    return (
        AdmissionDimension(
            DIVIDEND_ADMISSION_POLICY_VERSION,
            status,
            tuple(gates),
            reason_codes,
        ),
        hard_kills,
        unknowns,
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
    if candidate.issuer_evidence is not None:
        expiry_candidates.extend(
            (
                candidate.issuer_evidence.valid_until,
                candidate.issuer_evidence.event_coverage_through + timedelta(hours=8),
            )
        )
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
