from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from patientcapital.domain.discovery import (
    DISCOVERY_POLICY_VERSION,
    DIVIDEND_MARKET_POLICY_VERSION,
    select_market_candidates,
)
from patientcapital.marketdata.models import InstrumentKind, MarketCandidate
from patientcapital.research.models import (
    BalanceSheetStatus,
    CorporateActionStatus,
    DividendResearchEvidence,
    ResearchCitation,
    ResearchFactKind,
    ResearchScope,
)

NOW = datetime(2026, 8, 16, 9, 0, tzinfo=UTC)


def ofz(
    asset_id: str,
    *,
    price: str,
    maturity: date,
    yield_percent: str,
    turnover: str,
) -> MarketCandidate:
    return MarketCandidate(
        asset_id=asset_id,
        name=asset_id,
        kind=InstrumentKind.OFZ,
        currency="RUB",
        lot_size=1,
        unit_price=Decimal(price),
        price_as_of=NOW - timedelta(hours=1),
        max_age=timedelta(days=4),
        source_url=f"https://iss.moex.com/{asset_id}",
        classification_url="https://www.moex.com/ru/marketdata/",
        quote_kind="last_dirty",
        turnover=Decimal(turnover),
        maturity_date=maturity,
        yield_percent=Decimal(yield_percent),
        clean_price_percent=Decimal("80"),
        face_value=Decimal("1000"),
        accrued_interest=Decimal("20"),
        next_coupon_date=date(2026, 9, 23),
        coupon_percent=Decimal("12"),
    )


def market_screen(
    asset_id: str,
    *,
    price: str,
    turnover: str,
    historical_yield: str,
) -> MarketCandidate:
    research = DividendResearchEvidence(
        schema_version="dividend-market-evidence-v1",
        policy_version=DIVIDEND_MARKET_POLICY_VERSION,
        observed_at=NOW - timedelta(hours=1),
        max_age=timedelta(days=4),
        reporting_period_end=date(2025, 12, 31),
        profitable_years=None,
        dividend_years=4,
        payout_ratio_percent=None,
        balance_sheet_status=BalanceSheetStatus.UNKNOWN,
        governance_program_member=None,
        corporate_action_status=CorporateActionStatus.UNKNOWN,
        summary="MOEX market screen; issuer fundamentals remain unknown.",
        citations=(
            ResearchCitation(
                kind=ResearchFactKind.LISTING,
                title=f"Листинг {asset_id}",
                url=f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{asset_id}.json",
            ),
            ResearchCitation(
                kind=ResearchFactKind.DIVIDENDS,
                title=f"Дивиденды {asset_id}",
                url=f"https://iss.moex.com/iss/securities/{asset_id}/dividends.json",
            ),
        ),
        scope=ResearchScope.MARKET_SCREEN,
        annual_dividend_per_share=Decimal("30"),
        historical_dividend_yield_percent=Decimal(historical_yield),
        last_registry_close_date=date(2025, 7, 18),
        listing_level=1,
        unknown_facts=("profitability", "payout", "balance", "governance", "corporate_actions"),
    )
    return MarketCandidate(
        asset_id=asset_id,
        name=asset_id,
        kind=InstrumentKind.DIVIDEND_STOCK,
        currency="RUB",
        lot_size=10,
        unit_price=Decimal(price),
        price_as_of=NOW - timedelta(hours=1),
        max_age=timedelta(days=4),
        source_url=f"https://iss.moex.com/{asset_id}",
        classification_url="https://www.moex.com/ru/marketdata/",
        quote_kind="current",
        turnover=Decimal(turnover),
        research=research,
    )


def test_ofz_ranking_uses_current_yield_inside_five_year_window() -> None:
    candidates = (
        ofz(
            "OFZ-LIQUID",
            price="820",
            maturity=date(2031, 8, 20),
            yield_percent="14.50",
            turnover="900000000",
        ),
        ofz(
            "OFZ-YIELD",
            price="810",
            maturity=date(2031, 9, 1),
            yield_percent="15.80",
            turnover="300000000",
        ),
    )

    selection = select_market_candidates(
        candidates,
        contribution=Decimal("8000"),
        horizon_years=5,
        risk_level="balanced",
        calculated_at=NOW,
    )

    assert selection.policy_version == DISCOVERY_POLICY_VERSION == "market-intelligence-v1"
    assert selection.items[0].candidate.asset_id == "OFZ-YIELD"
    assert selection.items[0].rank_factors["yield_percent"] == "15.80"
    assert selection.items[0].score > 0
    assert "доходност" in selection.items[0].rationale.lower()


def test_budget_can_change_winner_and_candidate_order_cannot() -> None:
    expensive = ofz(
        "OFZ-EXPENSIVE",
        price="1200",
        maturity=date(2031, 8, 20),
        yield_percent="16.00",
        turnover="500000000",
    )
    affordable = ofz(
        "OFZ-AFFORDABLE",
        price="800",
        maturity=date(2031, 8, 20),
        yield_percent="15.00",
        turnover="400000000",
    )

    small = select_market_candidates(
        (expensive, affordable),
        contribution=Decimal("900"),
        horizon_years=5,
        risk_level="growth",
        calculated_at=NOW,
    )
    large = select_market_candidates(
        (affordable, expensive),
        contribution=Decimal("5000"),
        horizon_years=5,
        risk_level="growth",
        calculated_at=NOW,
    )
    reordered = select_market_candidates(
        (expensive, affordable),
        contribution=Decimal("5000"),
        horizon_years=5,
        risk_level="growth",
        calculated_at=NOW,
    )

    assert small.items[0].candidate.asset_id == "OFZ-AFFORDABLE"
    assert large.items[0].candidate.asset_id == "OFZ-EXPENSIVE"
    assert reordered.items[0].candidate.asset_id == large.items[0].candidate.asset_id


def test_dynamic_dividend_screen_ranks_current_market_candidates() -> None:
    selection = select_market_candidates(
        (
            market_screen("STOCK-LIQUID", price="200", turnover="900000000", historical_yield="8"),
            market_screen("STOCK-INCOME", price="150", turnover="400000000", historical_yield="12"),
        ),
        contribution=Decimal("8000"),
        horizon_years=5,
        risk_level="growth",
        calculated_at=NOW,
    )

    stock = selection.items[0]
    assert stock.candidate.asset_id == "STOCK-INCOME"
    assert stock.target_weight == Decimal("1.00000000")
    assert stock.candidate.research is not None
    assert stock.candidate.research.scope is ResearchScope.MARKET_SCREEN
    assert "полный фундаментальный аудит" in stock.rationale.lower()
    rejected = next(
        item for item in selection.rejected if item.candidate.asset_id == "STOCK-LIQUID"
    )
    assert rejected.score is not None
    assert "ranking" in rejected.reason
