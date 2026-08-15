from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from patientcapital.domain.discovery import DISCOVERY_POLICY_VERSION, select_market_candidates
from patientcapital.domain.errors import InvalidAllocationInput
from patientcapital.marketdata.models import InstrumentKind, MarketCandidate

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def candidate(
    asset_id: str,
    kind: InstrumentKind,
    *,
    price: str,
    turnover: str,
    maturity: date | None = None,
) -> MarketCandidate:
    return MarketCandidate(
        asset_id=asset_id,
        name=asset_id,
        kind=kind,
        currency="RUB",
        lot_size=1,
        unit_price=Decimal(price),
        price_as_of=NOW - timedelta(hours=12),
        max_age=timedelta(days=4),
        source_url=f"https://iss.moex.com/{asset_id}",
        classification_url="https://www.moex.com/msn/etf",
        quote_kind="last" if kind is InstrumentKind.OFZ else "current",
        turnover=Decimal(turnover),
        maturity_date=maturity,
        yield_percent=Decimal("15.10") if maturity else None,
        clean_price_percent=Decimal("78.00") if maturity else None,
        face_value=Decimal("1000.00") if maturity else None,
        accrued_interest=Decimal("30.00") if maturity else None,
    )


def test_five_year_balanced_policy_selects_liquid_near_maturity_ofz_and_index_fund() -> None:
    candidates = (
        candidate(
            "OFZ-NEAR",
            InstrumentKind.OFZ,
            price="810.00",
            turnover="100",
            maturity=date(2031, 8, 20),
        ),
        candidate(
            "OFZ-LIQUID",
            InstrumentKind.OFZ,
            price="820.00",
            turnover="900",
            maturity=date(2031, 10, 1),
        ),
        candidate("FUND-A", InstrumentKind.EQUITY_INDEX_FUND, price="110", turnover="100"),
        candidate("FUND-B", InstrumentKind.EQUITY_INDEX_FUND, price="120", turnover="800"),
    )

    selection = select_market_candidates(
        candidates,
        contribution=Decimal("8000.00"),
        horizon_years=5,
        risk_level="balanced",
        calculated_at=NOW,
    )

    assert selection.policy_version == DISCOVERY_POLICY_VERSION
    assert [(item.candidate.asset_id, item.target_weight) for item in selection.items] == [
        ("OFZ-LIQUID", Decimal("0.60000000")),
        ("FUND-B", Decimal("0.40000000")),
    ]
    assert "погаш" in selection.items[0].rationale.lower()
    assert "ликвид" in selection.items[1].rationale.lower()


def test_policy_renormalizes_to_affordable_class_in_small_budget() -> None:
    candidates = (
        candidate(
            "OFZ",
            InstrumentKind.OFZ,
            price="900.00",
            turnover="900",
            maturity=date(2031, 8, 20),
        ),
        candidate("FUND", InstrumentKind.EQUITY_INDEX_FUND, price="50", turnover="800"),
    )

    selection = select_market_candidates(
        candidates,
        contribution=Decimal("500.00"),
        horizon_years=5,
        risk_level="conservative",
        calculated_at=NOW,
    )

    assert [(item.candidate.asset_id, item.target_weight) for item in selection.items] == [
        ("FUND", Decimal("1.00000000"))
    ]


def test_policy_renormalizes_to_ofz_and_uses_far_maturity_fallback() -> None:
    selection = select_market_candidates(
        (
            candidate(
                "OFZ-FAR",
                InstrumentKind.OFZ,
                price="800",
                turnover="100",
                maturity=date(2034, 8, 15),
            ),
            candidate(
                "FUND-EXPENSIVE",
                InstrumentKind.EQUITY_INDEX_FUND,
                price="9000",
                turnover="1",
            ),
        ),
        contribution=Decimal("8000"),
        horizon_years=5,
        risk_level="growth",
        calculated_at=datetime(2024, 2, 29, 9, 0, tzinfo=UTC),
    )

    assert [(item.candidate.asset_id, item.target_weight) for item in selection.items] == [
        ("OFZ-FAR", Decimal("1.00000000"))
    ]


@pytest.mark.parametrize("horizon", [1, 4, 6, 15])
def test_versioned_policy_fails_loud_for_unsupported_horizon(horizon: int) -> None:
    with pytest.raises(InvalidAllocationInput) as captured:
        select_market_candidates(
            (
                candidate(
                    "OFZ",
                    InstrumentKind.OFZ,
                    price="800",
                    turnover="100",
                    maturity=date(2031, 8, 20),
                ),
            ),
            contribution=Decimal("8000"),
            horizon_years=horizon,
            risk_level="balanced",
            calculated_at=NOW,
        )

    assert captured.value.code == "UNSUPPORTED_DISCOVERY_HORIZON"


def test_policy_fails_when_no_candidate_fits_the_budget() -> None:
    with pytest.raises(InvalidAllocationInput) as captured:
        select_market_candidates(
            (
                candidate(
                    "OFZ",
                    InstrumentKind.OFZ,
                    price="900",
                    turnover="100",
                    maturity=date(2031, 8, 20),
                ),
            ),
            contribution=Decimal("100"),
            horizon_years=5,
            risk_level="balanced",
            calculated_at=NOW,
        )

    assert captured.value.code == "NO_AFFORDABLE_MARKET_CANDIDATE"


@pytest.mark.parametrize(
    ("risk_level", "contribution", "calculated_at", "code"),
    [
        ("unknown", Decimal("8000"), NOW, "UNSUPPORTED_RISK_LEVEL"),
        ("balanced", Decimal("0"), NOW, "INVALID_DISCOVERY_CONTRIBUTION"),
        ("balanced", Decimal("NaN"), NOW, "INVALID_DISCOVERY_CONTRIBUTION"),
        (
            "balanced",
            Decimal("8000"),
            datetime(2026, 8, 15, 9, 0),
            "INVALID_CALCULATION_TIME",
        ),
    ],
)
def test_policy_rejects_unknown_or_invalid_inputs(
    risk_level: str,
    contribution: Decimal,
    calculated_at: datetime,
    code: str,
) -> None:
    with pytest.raises(InvalidAllocationInput) as captured:
        select_market_candidates(
            (
                candidate(
                    "OFZ",
                    InstrumentKind.OFZ,
                    price="800",
                    turnover="100",
                    maturity=date(2031, 8, 20),
                ),
            ),
            contribution=contribution,
            horizon_years=5,
            risk_level=risk_level,
            calculated_at=calculated_at,
        )

    assert captured.value.code == code
