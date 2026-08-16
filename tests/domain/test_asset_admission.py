from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from patientcapital.domain.admission import (
    ADMISSION_POLICY_VERSION,
    LIQUIDITY_POLICY_VERSION,
    AdmissionStatus,
    LiquidityObservation,
    MarketLiquidityEvidence,
    compose_statuses,
    evaluate_asset_admission,
    evaluate_market_liquidity,
)
from patientcapital.domain.discovery import DIVIDEND_MARKET_POLICY_VERSION, DIVIDEND_POLICY_VERSION
from patientcapital.domain.errors import InvalidAllocationInput
from patientcapital.marketdata.models import InstrumentKind, MarketCandidate, MarketScan
from patientcapital.research.models import (
    BalanceSheetStatus,
    CorporateActionStatus,
    DividendResearchEvidence,
    ResearchCitation,
    ResearchFactKind,
    ResearchScope,
)

NOW = datetime(2026, 8, 16, 9, 0, tzinfo=UTC)


def liquidity(
    *,
    turnover: str = "100000000",
    traded_sessions: int = 20,
    spread_percent: str | None = "0.40",
    observed_at: datetime = NOW - timedelta(hours=1),
) -> MarketLiquidityEvidence:
    observations: list[LiquidityObservation] = []
    for index in range(20):
        traded = index < traded_sessions
        bid = Decimal("100") if spread_percent is not None else None
        if spread_percent is None:
            offer = None
        else:
            spread = Decimal(spread_percent)
            offer = (Decimal("20000") + spread * Decimal("100")) / (Decimal("200") - spread)
        observations.append(
            LiquidityObservation(
                session_date=date(2026, 8, 15) - timedelta(days=index),
                turnover_rub=Decimal(turnover) if traded else Decimal("0"),
                trades=1000 if traded else 0,
                bid=bid,
                offer=offer,
            )
        )
    return MarketLiquidityEvidence(
        policy_version=LIQUIDITY_POLICY_VERSION,
        observed_at=observed_at,
        max_age=timedelta(days=4),
        security_status="active",
        observations=tuple(observations),
        source_url="https://iss.moex.com/iss/history/test",
    )


def full_research(**overrides: object) -> DividendResearchEvidence:
    values: dict[str, object] = {
        "schema_version": "dividend-research-evidence-v1",
        "policy_version": DIVIDEND_POLICY_VERSION,
        "observed_at": NOW - timedelta(days=1),
        "max_age": timedelta(days=180),
        "reporting_period_end": date(2025, 12, 31),
        "profitable_years": 4,
        "dividend_years": 4,
        "payout_ratio_percent": Decimal("75"),
        "balance_sheet_status": BalanceSheetStatus.ADEQUATE_CAPITAL,
        "governance_program_member": True,
        "corporate_action_status": CorporateActionStatus.NO_MATERIAL_ACTION_IDENTIFIED,
        "summary": "Validated dividend-quality fixture.",
        "citations": tuple(
            ResearchCitation(kind=kind, title=kind.value, url=url)
            for kind, url in (
                (ResearchFactKind.FUNDAMENTALS, "https://www.moex.com/n98156"),
                (ResearchFactKind.DIVIDENDS, "https://www.moex.com/a2656"),
                (ResearchFactKind.GOVERNANCE, "https://www.moex.com/governance"),
                (ResearchFactKind.CORPORATE_ACTIONS, "https://www.moex.com/actions"),
            )
        ),
        "last_registry_close_date": date(2025, 7, 18),
    }
    values.update(overrides)
    return DividendResearchEvidence(**values)  # type: ignore[arg-type]


def equity(research: DividendResearchEvidence | None) -> MarketCandidate:
    return MarketCandidate(
        asset_id="EQUITY",
        name="Equity",
        kind=InstrumentKind.DIVIDEND_STOCK,
        currency="RUB",
        lot_size=10,
        unit_price=Decimal("100"),
        price_as_of=NOW - timedelta(hours=1),
        max_age=timedelta(days=4),
        source_url="https://iss.moex.com/iss/securities/EQUITY",
        classification_url="https://www.moex.com/ru/marketdata/",
        quote_kind="last",
        turnover=Decimal("100000000"),
        research=research,
        liquidity=liquidity(),
    )


def ofz(*, maturity_date: date, yield_percent: Decimal | None = Decimal("15")) -> MarketCandidate:
    return MarketCandidate(
        asset_id="OFZ",
        name="OFZ",
        kind=InstrumentKind.OFZ,
        currency="RUB",
        lot_size=1,
        unit_price=Decimal("900"),
        price_as_of=NOW - timedelta(hours=1),
        max_age=timedelta(days=4),
        source_url="https://iss.moex.com/iss/securities/OFZ",
        classification_url="https://www.moex.com/ru/marketdata/",
        quote_kind="last_dirty",
        turnover=Decimal("100000000"),
        maturity_date=maturity_date,
        yield_percent=yield_percent,
        clean_price_percent=Decimal("88"),
        face_value=Decimal("1000"),
        accrued_interest=Decimal("20"),
        liquidity=liquidity(turnover="100000000"),
    )


def fund(*, classification_url: str) -> MarketCandidate:
    return MarketCandidate(
        asset_id="FUND",
        name="Fund",
        kind=InstrumentKind.EQUITY_INDEX_FUND,
        currency="RUB",
        lot_size=1,
        unit_price=Decimal("100"),
        price_as_of=NOW - timedelta(hours=1),
        max_age=timedelta(days=4),
        source_url="https://iss.moex.com/iss/securities/FUND",
        classification_url=classification_url,
        quote_kind="last",
        turnover=Decimal("10000000"),
        liquidity=liquidity(turnover="10000000"),
    )


@pytest.mark.parametrize(
    ("kind", "turnover", "expected"),
    [
        (InstrumentKind.DIVIDEND_STOCK, "100000000", AdmissionStatus.ELIGIBLE),
        (InstrumentKind.DIVIDEND_STOCK, "20000000", AdmissionStatus.WATCH),
        (InstrumentKind.DIVIDEND_STOCK, "1000000", AdmissionStatus.REJECT),
        (InstrumentKind.OFZ, "30000000", AdmissionStatus.ELIGIBLE),
        (InstrumentKind.EQUITY_INDEX_FUND, "2000000", AdmissionStatus.WATCH),
    ],
)
def test_rolling_liquidity_uses_class_thresholds(
    kind: InstrumentKind, turnover: str, expected: AdmissionStatus
) -> None:
    result = evaluate_market_liquidity(kind, liquidity(turnover=turnover), calculated_at=NOW)

    assert result.policy_version == LIQUIDITY_POLICY_VERSION
    assert result.status is expected
    assert {gate.gate_id for gate in result.gates} == {
        "security_status",
        "observation_window",
        "trade_coverage",
        "median_turnover",
        "median_spread",
        "evidence_freshness",
        "last_completed_session",
    }


def test_high_one_day_turnover_cannot_hide_sparse_trading() -> None:
    result = evaluate_market_liquidity(
        InstrumentKind.DIVIDEND_STOCK,
        liquidity(turnover="5000000000", traded_sessions=3),
        calculated_at=NOW,
    )

    assert result.status is AdmissionStatus.REJECT
    assert "LIQUIDITY_TRADE_COVERAGE_REJECT" in result.reason_codes


def test_missing_unsupported_and_incomplete_liquidity_are_explicit() -> None:
    missing = evaluate_market_liquidity(
        InstrumentKind.PUBLIC_EQUITY, None, calculated_at=NOW
    )
    unsupported = evaluate_market_liquidity(
        InstrumentKind.PUBLIC_EQUITY,
        replace(liquidity(), policy_version="market-liquidity-old"),
        calculated_at=NOW,
    )
    incomplete = evaluate_market_liquidity(
        InstrumentKind.PUBLIC_EQUITY,
        replace(liquidity(), observations=liquidity().observations[:19]),
        calculated_at=NOW,
    )

    assert missing.reason_codes == ("LIQUIDITY_EVIDENCE_MISSING",)
    assert unsupported.reason_codes == ("LIQUIDITY_POLICY_UNSUPPORTED",)
    assert incomplete.status is AdmissionStatus.UNKNOWN
    assert "LIQUIDITY_WINDOW_INCOMPLETE" in incomplete.reason_codes
    assert "LIQUIDITY_TRADE_COVERAGE_UNKNOWN" in incomplete.reason_codes


@pytest.mark.parametrize(
    ("security_status", "expected_reason"),
    [
        ("suspended", "LIQUIDITY_SECURITY_SUSPENDED"),
        ("delisted", "LIQUIDITY_SECURITY_DELISTED"),
        ("unknown", "LIQUIDITY_SECURITY_STATUS_UNKNOWN"),
    ],
)
def test_security_status_is_a_material_gate(
    security_status: str, expected_reason: str
) -> None:
    result = evaluate_market_liquidity(
        InstrumentKind.PUBLIC_EQUITY,
        replace(liquidity(), security_status=security_status),
        calculated_at=NOW,
    )

    assert expected_reason in result.reason_codes


@pytest.mark.parametrize(
    ("spread_percent", "expected_status", "expected_reason"),
    [
        ("1.00", AdmissionStatus.WATCH, "LIQUIDITY_SPREAD_WATCH"),
        ("2.00", AdmissionStatus.REJECT, "LIQUIDITY_SPREAD_REJECT"),
    ],
)
def test_confirmed_spread_changes_liquidity_status(
    spread_percent: str,
    expected_status: AdmissionStatus,
    expected_reason: str,
) -> None:
    result = evaluate_market_liquidity(
        InstrumentKind.PUBLIC_EQUITY,
        liquidity(spread_percent=spread_percent),
        calculated_at=NOW,
    )

    assert result.status is expected_status
    assert expected_reason in result.reason_codes


def test_missing_spread_is_visible_advisory_but_stale_series_remains_unknown() -> None:
    missing_spread = evaluate_market_liquidity(
        InstrumentKind.OFZ, liquidity(spread_percent=None), calculated_at=NOW
    )
    stale = evaluate_market_liquidity(
        InstrumentKind.OFZ,
        liquidity(observed_at=NOW - timedelta(days=5)),
        calculated_at=NOW,
    )

    assert missing_spread.status is AdmissionStatus.ELIGIBLE
    spread_gate = next(gate for gate in missing_spread.gates if gate.gate_id == "median_spread")
    assert spread_gate.status is AdmissionStatus.UNKNOWN
    assert spread_gate.material is False
    assert stale.status is AdmissionStatus.UNKNOWN


def test_recent_fetch_cannot_make_old_market_sessions_fresh() -> None:
    recent_fetch_with_old_sessions = liquidity(observed_at=NOW)
    old_observations = tuple(
        LiquidityObservation(
            session_date=item.session_date - timedelta(days=10),
            turnover_rub=item.turnover_rub,
            trades=item.trades,
            bid=item.bid,
            offer=item.offer,
        )
        for item in recent_fetch_with_old_sessions.observations
    )
    evidence = MarketLiquidityEvidence(
        policy_version=recent_fetch_with_old_sessions.policy_version,
        observed_at=recent_fetch_with_old_sessions.observed_at,
        max_age=recent_fetch_with_old_sessions.max_age,
        security_status=recent_fetch_with_old_sessions.security_status,
        observations=old_observations,
        source_url=recent_fetch_with_old_sessions.source_url,
    )

    result = evaluate_market_liquidity(
        InstrumentKind.DIVIDEND_STOCK, evidence, calculated_at=NOW
    )

    assert result.status is AdmissionStatus.UNKNOWN
    assert "LIQUIDITY_LAST_SESSION_STALE" in result.reason_codes


def test_status_composition_is_fail_closed_and_order_invariant() -> None:
    statuses = (
        AdmissionStatus.ELIGIBLE,
        AdmissionStatus.WATCH,
        AdmissionStatus.UNKNOWN,
        AdmissionStatus.REJECT,
    )

    assert compose_statuses(statuses) is AdmissionStatus.REJECT
    assert compose_statuses(tuple(reversed(statuses))) is AdmissionStatus.REJECT
    assert compose_statuses((AdmissionStatus.ELIGIBLE, AdmissionStatus.UNKNOWN)) is (
        AdmissionStatus.UNKNOWN
    )


def test_market_screen_is_research_only_even_when_history_looks_attractive() -> None:
    screen = full_research(
        schema_version="dividend-market-evidence-v1",
        policy_version=DIVIDEND_MARKET_POLICY_VERSION,
        scope=ResearchScope.MARKET_SCREEN,
        reporting_period_end=date(2025, 7, 18),
        profitable_years=None,
        payout_ratio_percent=None,
        balance_sheet_status=BalanceSheetStatus.UNKNOWN,
        governance_program_member=None,
        corporate_action_status=CorporateActionStatus.UNKNOWN,
        annual_dividend_per_share=Decimal("50"),
        historical_dividend_yield_percent=Decimal("50"),
        listing_level=1,
        unknown_facts=("profitability", "payout", "balance", "governance", "corporate_actions"),
        citations=(
            ResearchCitation(
                kind=ResearchFactKind.LISTING,
                title="listing",
                url="https://iss.moex.com/iss/securities/EQUITY",
            ),
            ResearchCitation(
                kind=ResearchFactKind.DIVIDENDS,
                title="dividends",
                url="https://iss.moex.com/iss/securities/EQUITY/dividends.json",
            ),
        ),
    )

    profile = evaluate_asset_admission(equity(screen), calculated_at=NOW)

    assert profile.policy_version == ADMISSION_POLICY_VERSION
    assert profile.overall_status is AdmissionStatus.UNKNOWN
    assert "ADMISSION_RESEARCH_ONLY" in profile.reason_codes


def test_old_dividend_fact_does_not_become_fresh_when_downloaded_today() -> None:
    profile = evaluate_asset_admission(
        equity(full_research(observed_at=NOW, last_registry_close_date=date(2022, 7, 18))),
        calculated_at=NOW,
    )

    assert profile.overall_status is AdmissionStatus.UNKNOWN
    assert "DIVIDEND_FACT_STALE" in profile.reason_codes


def test_binding_material_corporate_action_is_a_dividend_strategy_hard_kill() -> None:
    profile = evaluate_asset_admission(
        equity(full_research(corporate_action_status=CorporateActionStatus.MATERIAL)),
        calculated_at=NOW,
    )

    assert profile.overall_status is AdmissionStatus.REJECT
    assert "DIVIDEND_MATERIAL_CORPORATE_ACTION" in profile.hard_kills


@pytest.mark.parametrize(
    ("overrides", "expected_status", "expected_reason"),
    [
        (
            {"observed_at": NOW - timedelta(days=181)},
            AdmissionStatus.UNKNOWN,
            "ADMISSION_RESEARCH_STALE_OR_UNSUPPORTED",
        ),
        (
            {"corporate_action_status": CorporateActionStatus.UNKNOWN},
            AdmissionStatus.UNKNOWN,
            "DIVIDEND_CORPORATE_ACTION_UNKNOWN",
        ),
        (
            {"last_registry_close_date": None},
            AdmissionStatus.UNKNOWN,
            "DIVIDEND_FACT_STALE",
        ),
        (
            {"profitable_years": 2},
            AdmissionStatus.REJECT,
            "DIVIDEND_PROFITABILITY_FAIL",
        ),
        (
            {"dividend_years": 2},
            AdmissionStatus.REJECT,
            "DIVIDEND_CONTINUITY_FAIL",
        ),
        (
            {"payout_ratio_percent": Decimal("101")},
            AdmissionStatus.REJECT,
            "DIVIDEND_PAYOUT_FAIL",
        ),
        (
            {"balance_sheet_status": BalanceSheetStatus.CONCERN},
            AdmissionStatus.REJECT,
            "DIVIDEND_BALANCE_FAIL",
        ),
        (
            {"balance_sheet_status": BalanceSheetStatus.UNKNOWN},
            AdmissionStatus.UNKNOWN,
            "DIVIDEND_BALANCE_UNKNOWN",
        ),
        (
            {"governance_program_member": False},
            AdmissionStatus.REJECT,
            "DIVIDEND_GOVERNANCE_FAIL",
        ),
        ({}, AdmissionStatus.ELIGIBLE, "DIVIDEND_QUALITY_PASS"),
    ],
)
def test_full_quality_equity_admission_gates(
    overrides: dict[str, object],
    expected_status: AdmissionStatus,
    expected_reason: str,
) -> None:
    profile = evaluate_asset_admission(
        equity(full_research(**overrides)), calculated_at=NOW
    )

    assert profile.overall_status is expected_status
    assert expected_reason in profile.reason_codes


def test_class_specific_investment_unknowns_are_fail_closed() -> None:
    unknown_ofz = evaluate_asset_admission(
        ofz(maturity_date=date(2031, 8, 16), yield_percent=None), calculated_at=NOW
    )
    expired_ofz = evaluate_asset_admission(
        ofz(maturity_date=date(2026, 8, 16)), calculated_at=NOW
    )
    unknown_fund = evaluate_asset_admission(
        fund(classification_url="https://www.moex.com/ru/marketdata/"),
        calculated_at=NOW,
    )
    research_queue = evaluate_asset_admission(
        MarketCandidate(
            asset_id="QUEUE",
            name="Queue",
            kind=InstrumentKind.PUBLIC_EQUITY,
            currency="RUB",
            lot_size=1,
            unit_price=Decimal("100"),
            price_as_of=NOW,
            max_age=timedelta(days=4),
            source_url="https://iss.moex.com/iss/securities/QUEUE",
            classification_url="https://www.moex.com/ru/marketdata/",
            quote_kind="last",
            turnover=Decimal("1"),
        ),
        calculated_at=NOW,
    )

    assert unknown_ofz.investment.reason_codes == ("OFZ_TERMS_UNKNOWN",)
    assert expired_ofz.investment.reason_codes == ("OFZ_TERMS_UNKNOWN",)
    assert unknown_fund.investment.reason_codes == ("FUND_CLASSIFICATION_UNKNOWN",)
    assert research_queue.overall_status is AdmissionStatus.UNKNOWN
    assert research_queue.liquidity.reason_codes == ("LIQUIDITY_EVIDENCE_MISSING",)


def test_liquidity_evidence_rejects_duplicate_sessions() -> None:
    evidence = liquidity()
    duplicate = (evidence.observations[0],) * 20
    with pytest.raises(InvalidAllocationInput, match="distinct"):
        MarketLiquidityEvidence(
            policy_version=LIQUIDITY_POLICY_VERSION,
            observed_at=NOW,
            max_age=timedelta(days=4),
            security_status="active",
            observations=duplicate,
            source_url="https://iss.moex.com/iss/history/test",
        )


@pytest.mark.parametrize(
    "observation",
    [
        {"turnover_rub": Decimal("-1"), "trades": 1},
        {"turnover_rub": Decimal("1"), "trades": True},
        {"turnover_rub": Decimal("1"), "trades": 1, "bid": Decimal("1")},
        {
            "turnover_rub": Decimal("1"),
            "trades": 1,
            "bid": Decimal("2"),
            "offer": Decimal("1"),
        },
    ],
)
def test_liquidity_observation_rejects_invalid_market_facts(
    observation: dict[str, object],
) -> None:
    with pytest.raises(InvalidAllocationInput):
        LiquidityObservation(session_date=date(2026, 8, 15), **observation)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "overrides",
    [
        {"policy_version": ""},
        {"observed_at": datetime(2026, 8, 16, 9, 0)},
        {"max_age": timedelta(0)},
        {"security_status": "halted"},
        {"observations": ()},
        {"source_url": "https://example.com/history"},
    ],
)
def test_liquidity_evidence_rejects_invalid_provenance(
    overrides: dict[str, object],
) -> None:
    base = liquidity()
    values: dict[str, object] = {
        "policy_version": base.policy_version,
        "observed_at": base.observed_at,
        "max_age": base.max_age,
        "security_status": base.security_status,
        "observations": base.observations,
        "source_url": base.source_url,
    }
    values.update(overrides)

    with pytest.raises(InvalidAllocationInput):
        MarketLiquidityEvidence(**values)  # type: ignore[arg-type]


def test_liquidity_freshness_rejects_naive_calculation_time() -> None:
    assert liquidity().is_fresh_at(datetime(2026, 8, 16, 9, 0)) is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"policy_version": ""},
        {"observed_at": datetime(2026, 8, 16, 9, 0)},
        {"universe_size": 0},
        {"enriched_count": -1},
        {"kind_counts": {"public_equity": -1}},
    ],
)
def test_market_scan_rejects_invalid_coverage_contract(overrides: dict[str, object]) -> None:
    values: dict[str, object] = {
        "policy_version": "scan-v1",
        "observed_at": NOW,
        "candidates": (fund(classification_url="https://www.moex.com/msn/etf"),),
        "universe_size": 1,
        "kind_counts": {"equity_index_fund": 1},
        "enriched_count": 0,
    }
    values.update(overrides)

    with pytest.raises(InvalidAllocationInput):
        MarketScan(**values)  # type: ignore[arg-type]
