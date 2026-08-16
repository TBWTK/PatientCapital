from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from patientcapital.domain.discovery import (
    DISCOVERY_POLICY_VERSION,
    DIVIDEND_POLICY_VERSION,
    select_market_candidates,
)
from patientcapital.domain.errors import InvalidAllocationInput
from patientcapital.marketdata.models import (
    InstrumentKind,
    LiquidityObservation,
    MarketCandidate,
    MarketLiquidityEvidence,
)
from patientcapital.research.models import (
    BalanceSheetStatus,
    CorporateActionStatus,
    DividendResearchEvidence,
    ResearchCitation,
    ResearchFactKind,
)

NOW = datetime(2026, 8, 16, 9, 0, tzinfo=UTC)


def admitted_liquidity(
    kind: InstrumentKind, *, turnover: str | None = None
) -> MarketLiquidityEvidence:
    rolling_turnover = turnover or (
        "100000000" if kind is not InstrumentKind.EQUITY_INDEX_FUND else "10000000"
    )
    return MarketLiquidityEvidence(
        policy_version="market-liquidity-v2",
        observed_at=NOW - timedelta(hours=1),
        max_age=timedelta(days=4),
        security_status="active",
        observations=tuple(
            LiquidityObservation(
                session_date=date(2026, 8, 15) - timedelta(days=index),
                turnover_rub=Decimal(rolling_turnover),
                trades=1000,
                bid=Decimal("100"),
                offer=Decimal("100.4"),
            )
            for index in range(20)
        ),
        source_url="https://iss.moex.com/iss/history/test",
    )


def evidence(**overrides: object) -> DividendResearchEvidence:
    values: dict[str, object] = {
        "schema_version": "dividend-research-evidence-v1",
        "policy_version": DIVIDEND_POLICY_VERSION,
        "observed_at": NOW - timedelta(days=1),
        "max_age": timedelta(days=180),
        "reporting_period_end": date(2025, 12, 31),
        "profitable_years": 4,
        "dividend_years": 4,
        "payout_ratio_percent": Decimal("75.00"),
        "balance_sheet_status": BalanceSheetStatus.NO_DEBT,
        "governance_program_member": True,
        "corporate_action_status": CorporateActionStatus.NO_MATERIAL_ACTION_IDENTIFIED,
        "summary": (
            "Положительная прибыль, покрытый дивиденд и отсутствие долга подтверждены "
            "первичными источниками; dividend capture не используется."
        ),
        "citations": tuple(
            ResearchCitation(kind=kind, title=kind.value, url=url)
            for kind, url in (
                (ResearchFactKind.FUNDAMENTALS, "https://www.moex.com/n98156"),
                (ResearchFactKind.DIVIDENDS, "https://www.moex.com/a2656"),
                (
                    ResearchFactKind.GOVERNANCE,
                    "https://www.moex.com/programma-sozdaniya-aktsionernoj-stoimosti-publichnyh-aktsionernyh-obschestv",
                ),
                (
                    ResearchFactKind.CORPORATE_ACTIONS,
                    "https://www.moex.com/povtornoe-godovoe-zasedanie-obschego-sobraniya-aktsionerov",
                ),
            )
        ),
        "last_registry_close_date": date(2025, 7, 18),
    }
    values.update(overrides)
    return DividendResearchEvidence(**values)  # type: ignore[arg-type]


def candidate(
    asset_id: str,
    kind: InstrumentKind,
    *,
    price: str,
    turnover: str,
    research: DividendResearchEvidence | None = None,
    maturity: date | None = None,
    currency: str = "RUB",
    market_liquidity: MarketLiquidityEvidence | None = None,
) -> MarketCandidate:
    return MarketCandidate(
        asset_id=asset_id,
        name=asset_id,
        kind=kind,
        currency=currency,
        lot_size=1,
        unit_price=Decimal(price),
        price_as_of=NOW - timedelta(hours=1),
        max_age=timedelta(days=4),
        source_url=f"https://iss.moex.com/{asset_id}",
        classification_url=(
            "https://www.moex.com/msn/etf"
            if kind is InstrumentKind.EQUITY_INDEX_FUND
            else "https://www.moex.com/ru/marketdata/"
        ),
        quote_kind="last_dirty" if maturity is not None else "current",
        turnover=Decimal(turnover),
        maturity_date=maturity,
        yield_percent=Decimal("15") if maturity is not None else None,
        clean_price_percent=Decimal("77") if maturity is not None else None,
        face_value=Decimal("1000") if maturity is not None else None,
        accrued_interest=Decimal("30") if maturity is not None else None,
        research=research,
        liquidity=market_liquidity or admitted_liquidity(kind),
    )


def test_growth_policy_admits_source_backed_dividend_stock_with_concentration_cap() -> None:
    selection = select_market_candidates(
        (
            candidate(
                "OFZ",
                InstrumentKind.OFZ,
                price="800",
                turnover="900",
                maturity=date(2031, 8, 20),
            ),
            candidate("FUND", InstrumentKind.EQUITY_INDEX_FUND, price="100", turnover="800"),
            candidate(
                "MOEX",
                InstrumentKind.DIVIDEND_STOCK,
                price="155",
                turnover="1000000000",
                research=evidence(),
            ),
        ),
        contribution=Decimal("8000"),
        horizon_years=5,
        risk_level="growth",
        calculated_at=NOW,
    )

    assert selection.policy_version == DISCOVERY_POLICY_VERSION
    assert [(item.candidate.asset_id, item.target_weight) for item in selection.items] == [
        ("OFZ", Decimal("0.40000000")),
        ("FUND", Decimal("0.40000000")),
        ("MOEX", Decimal("0.20000000")),
    ]
    stock = selection.items[-1]
    assert stock.candidate.research is not None
    assert stock.candidate.research.policy_version == DIVIDEND_POLICY_VERSION
    assert "дивиденд" in stock.rationale.lower()


@pytest.mark.parametrize(
    ("research", "turnover", "reason"),
    [
        (evidence(observed_at=NOW - timedelta(days=181)), "1000000000", "просроч"),
        (evidence(profitable_years=2), "1000000000", "прибыл"),
        (evidence(dividend_years=2), "1000000000", "дивиденд"),
        (evidence(payout_ratio_percent=Decimal("120")), "1000000000", "покры"),
        (
            evidence(balance_sheet_status=BalanceSheetStatus.CONCERN),
            "1000000000",
            "баланс",
        ),
        (evidence(governance_program_member=False), "1000000000", "управлен"),
        (
            evidence(corporate_action_status=CorporateActionStatus.MATERIAL),
            "1000000000",
            "корпоратив",
        ),
    ],
)
def test_dividend_gate_rejects_each_material_unknown(
    research: DividendResearchEvidence, turnover: str, reason: str
) -> None:
    selection = select_market_candidates(
        (
            candidate("FUND", InstrumentKind.EQUITY_INDEX_FUND, price="100", turnover="800"),
            candidate(
                "STOCK",
                InstrumentKind.DIVIDEND_STOCK,
                price="155",
                turnover=turnover,
                research=research,
            ),
        ),
        contribution=Decimal("8000"),
        horizon_years=5,
        risk_level="growth",
        calculated_at=NOW,
    )

    rejected = next(item for item in selection.rejected if item.candidate.asset_id == "STOCK")
    assert reason in rejected.reason.lower()
    assert [(item.candidate.asset_id, item.target_weight) for item in selection.items] == [
        ("FUND", Decimal("1.00000000"))
    ]


def test_dividend_gate_uses_rolling_liquidity_instead_of_current_turnover() -> None:
    selection = select_market_candidates(
        (
            candidate("FUND", InstrumentKind.EQUITY_INDEX_FUND, price="100", turnover="800"),
            candidate(
                "STOCK",
                InstrumentKind.DIVIDEND_STOCK,
                price="155",
                turnover="1000000000",
                research=evidence(),
                market_liquidity=admitted_liquidity(
                    InstrumentKind.DIVIDEND_STOCK, turnover="1000000"
                ),
            ),
        ),
        contribution=Decimal("8000"),
        horizon_years=5,
        risk_level="growth",
        calculated_at=NOW,
    )

    rejected = next(item for item in selection.rejected if item.candidate.asset_id == "STOCK")
    assert "LIQUIDITY_TURNOVER_REJECT" in rejected.reason


def test_dividend_candidate_requires_typed_research_evidence() -> None:
    with pytest.raises(InvalidAllocationInput) as captured:
        candidate("STOCK", InstrumentKind.DIVIDEND_STOCK, price="155", turnover="1000000000")

    assert captured.value.code == "INVALID_MARKET_CANDIDATE"


def test_research_evidence_requires_primary_https_sources_for_all_gate_categories() -> None:
    with pytest.raises(InvalidAllocationInput) as captured:
        evidence(
            citations=(
                ResearchCitation(
                    kind=ResearchFactKind.FUNDAMENTALS,
                    title="untrusted",
                    url="https://example.com/opinion",
                ),
            )
        )

    assert captured.value.code == "INVALID_RESEARCH_EVIDENCE"


@pytest.mark.parametrize(
    "overrides",
    [
        {"schema_version": ""},
        {"policy_version": ""},
        {"observed_at": datetime(2026, 8, 16, 9, 0)},
        {"max_age": timedelta(0)},
        {"reporting_period_end": date(2027, 1, 1)},
        {"profitable_years": True},
        {"dividend_years": -1},
        {"payout_ratio_percent": Decimal("NaN")},
        {"payout_ratio_percent": Decimal("-1")},
        {"governance_program_member": 1},
        {"summary": " "},
    ],
)
def test_research_evidence_rejects_invalid_material_fields(overrides: dict[str, object]) -> None:
    with pytest.raises(InvalidAllocationInput) as captured:
        evidence(**overrides)

    assert captured.value.code == "INVALID_RESEARCH_EVIDENCE"


def test_research_citation_requires_a_title_and_freshness_requires_aware_time() -> None:
    with pytest.raises(InvalidAllocationInput) as captured:
        ResearchCitation(
            kind=ResearchFactKind.FUNDAMENTALS,
            title=" ",
            url="https://www.moex.com/n98156",
        )
    assert captured.value.code == "INVALID_RESEARCH_EVIDENCE"
    assert evidence().is_fresh_at(datetime(2026, 8, 16, 9, 0)) is False
    assert evidence().is_fresh_at(NOW - timedelta(days=2)) is False


def test_dividend_policy_rejects_wrong_policy_currency_and_unaffordable_lot() -> None:
    candidates = (
        candidate(
            "WRONG-POLICY",
            InstrumentKind.DIVIDEND_STOCK,
            price="100",
            turnover="1000000000",
            research=evidence(policy_version="other-policy-v1"),
        ),
        candidate(
            "FOREIGN",
            InstrumentKind.DIVIDEND_STOCK,
            price="100",
            turnover="1000000000",
            research=evidence(),
            currency="USD",
        ),
        candidate(
            "EXPENSIVE",
            InstrumentKind.DIVIDEND_STOCK,
            price="9000",
            turnover="1000000000",
            research=evidence(),
        ),
        candidate("FUND", InstrumentKind.EQUITY_INDEX_FUND, price="100", turnover="800"),
    )

    selection = select_market_candidates(
        candidates,
        contribution=Decimal("8000"),
        horizon_years=5,
        risk_level="growth",
        calculated_at=NOW,
    )

    reasons = {item.candidate.asset_id: item.reason for item in selection.rejected}
    assert "версии" in reasons["WRONG-POLICY"]
    assert "Валюта" in reasons["FOREIGN"]
    assert "лота" in reasons["EXPENSIVE"]


def test_dividend_policy_ranks_two_eligible_stocks_by_liquidity() -> None:
    selection = select_market_candidates(
        (
            candidate("FUND", InstrumentKind.EQUITY_INDEX_FUND, price="100", turnover="800"),
            candidate(
                "STOCK-A",
                InstrumentKind.DIVIDEND_STOCK,
                price="100",
                turnover="1000000000",
                research=evidence(),
            ),
            candidate(
                "STOCK-B",
                InstrumentKind.DIVIDEND_STOCK,
                price="100",
                turnover="900000000",
                research=evidence(),
            ),
        ),
        contribution=Decimal("8000"),
        horizon_years=5,
        risk_level="growth",
        calculated_at=NOW,
    )

    assert any(item.candidate.asset_id == "STOCK-A" for item in selection.items)
    rejected = next(item for item in selection.rejected if item.candidate.asset_id == "STOCK-B")
    assert "ranking" in rejected.reason
