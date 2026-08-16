from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from patientcapital.domain.errors import InvalidAllocationInput
from patientcapital.marketdata.errors import MarketDataError
from patientcapital.marketdata.models import InstrumentKind, MarketCandidate
from patientcapital.marketdata.moex import (
    MoexIssProvider,
    _date,
    _decimal,
    _integer,
    _rows,
    _string,
    _timestamp,
)
from patientcapital.research.corpus import MOEX_DIVIDEND_RESEARCH

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def _candidate(**overrides: object) -> MarketCandidate:
    values: dict[str, object] = {
        "asset_id": "EQMX",
        "name": "Индекс МосБиржи",
        "kind": InstrumentKind.EQUITY_INDEX_FUND,
        "currency": "RUB",
        "lot_size": 1,
        "unit_price": Decimal("117.35"),
        "price_as_of": NOW,
        "max_age": timedelta(days=4),
        "source_url": "https://iss.moex.com/EQMX",
        "classification_url": "https://www.moex.com/msn/etf",
        "quote_kind": "current",
        "turnover": Decimal("100"),
    }
    values.update(overrides)
    return MarketCandidate(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"asset_id": " "}, "asset id and name"),
        ({"name": " "}, "asset id and name"),
        ({"source_url": "http://iss.moex.com/EQMX"}, "HTTPS"),
        ({"classification_url": "marketdata"}, "HTTPS"),
        ({"quote_kind": " "}, "quote kind"),
        ({"lot_size": True}, "lot size"),
        ({"lot_size": 0}, "lot size"),
        ({"unit_price": Decimal("NaN")}, "unit price"),
        ({"unit_price": Decimal("0")}, "unit price"),
        ({"turnover": Decimal("Infinity")}, "turnover"),
        ({"turnover": Decimal("-1")}, "turnover"),
        ({"price_as_of": datetime(2026, 8, 15, 9, 0)}, "timestamp"),
        ({"max_age": timedelta(0)}, "max age"),
        ({"yield_percent": Decimal("NaN")}, "yield"),
    ],
)
def test_market_candidate_rejects_invalid_material_fact(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(InvalidAllocationInput, match=message) as captured:
        _candidate(**overrides)

    assert captured.value.code == "INVALID_MARKET_CANDIDATE"


def test_ofz_requires_all_dirty_price_components() -> None:
    with pytest.raises(InvalidAllocationInput) as captured:
        _candidate(kind=InstrumentKind.OFZ, maturity_date=date(2031, 8, 15))

    assert captured.value.code == "INVALID_MARKET_CANDIDATE"


def test_non_dividend_candidate_rejects_dividend_research_evidence() -> None:
    with pytest.raises(InvalidAllocationInput) as captured:
        _candidate(research=MOEX_DIVIDEND_RESEARCH)

    assert captured.value.code == "INVALID_MARKET_CANDIDATE"


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: _decimal(None, field="PRICE"), "PRICE is missing"),
        (lambda: _decimal(True, field="PRICE"), "PRICE is missing"),
        (lambda: _decimal("not-a-number", field="PRICE"), "not decimal"),
        (lambda: _decimal("Infinity", field="PRICE"), "valid range"),
        (lambda: _decimal("0", field="PRICE", positive=True), "valid range"),
        (lambda: _integer(True, field="LOTSIZE"), "not an integer"),
        (lambda: _integer("1.5", field="LOTSIZE"), "not an integer"),
        (lambda: _integer(0, field="LOTSIZE"), "must be positive"),
        (lambda: _timestamp(None), "SYSTIME is missing"),
        (lambda: _timestamp("15.08.2026"), "unknown format"),
        (lambda: _date(None, field="MATDATE"), "MATDATE is missing"),
        (lambda: _date("2031/08/15", field="MATDATE"), "unknown format"),
        (lambda: _string({}, "SECID"), "SECID is missing"),
    ],
)
def test_moex_scalar_parser_fails_closed(call: Callable[[], object], message: str) -> None:
    with pytest.raises(MarketDataError, match=message):
        call()


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"securities": []},
        {"securities": {"columns": [], "data": []}},
        {"securities": {"columns": [1], "data": []}},
        {"securities": {"columns": ["SECID"], "data": {}}},
        {"securities": {"columns": ["SECID"], "data": [["A", "extra"]]}},
    ],
)
def test_moex_table_parser_rejects_invalid_shapes(payload: object) -> None:
    with pytest.raises(MarketDataError) as captured:
        _rows(payload, "securities")

    assert captured.value.code == "MOEX_INVALID_RESPONSE"


def test_provider_rejects_non_allowlisted_base_and_naive_time() -> None:
    with pytest.raises(ValueError, match="allowlisted"):
        MoexIssProvider(base_url="https://example.com/iss")

    with pytest.raises(MarketDataError) as captured:
        MoexIssProvider().discover(calculated_at=datetime(2026, 8, 15, 9, 0))

    assert captured.value.code == "INVALID_CALCULATION_TIME"
