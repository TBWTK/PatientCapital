from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from patientcapital.marketdata.errors import MarketDataError
from patientcapital.marketdata.models import InstrumentKind
from patientcapital.marketdata.moex import MoexIssProvider

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def _block(columns: list[str], data: list[list[object]]) -> dict[str, object]:
    return {"columns": columns, "data": data}


def _handler(request: httpx.Request) -> httpx.Response:
    if "/bonds/boards/TQOB/" in request.url.path:
        return httpx.Response(
            200,
            json={
                "securities": _block(
                    [
                        "SECID",
                        "SHORTNAME",
                        "LOTSIZE",
                        "STATUS",
                        "FACEVALUE",
                        "FACEUNIT",
                        "ACCRUEDINT",
                        "MATDATE",
                        "COUPONPERCENT",
                    ],
                    [
                        [
                            "SU26218RMFS6",
                            "ОФЗ 26218",
                            1,
                            "A",
                            1000,
                            "SUR",
                            33.76,
                            "2031-09-17",
                            8.5,
                        ]
                    ],
                ),
                "marketdata": _block(
                    ["SECID", "LAST", "MARKETPRICE", "YIELD", "VALTODAY", "SYSTIME"],
                    [["SU26218RMFS6", 78.445, 78.4, 15.19, 742285912, "2026-08-14 23:50:44"]],
                ),
            },
        )
    asset_id = request.url.path.rsplit("/", 1)[-1].removesuffix(".json")
    is_stock = asset_id == "MOEX"
    return httpx.Response(
        200,
        json={
            "securities": _block(
                [
                    "SECID",
                    "SHORTNAME",
                    "LOTSIZE",
                    "STATUS",
                    "CURRENCYID",
                    "SECTYPE",
                    "INSTRID",
                    "ISIN",
                ],
                [[
                    asset_id,
                    "МосБиржа" if is_stock else f"{asset_id} ETF",
                    10 if is_stock else 1,
                    "A",
                    "SUR",
                    "1" if is_stock else "J",
                    "EQIN" if is_stock else "IFTF",
                    "RU000A0JR4A1" if is_stock else "RU000TEST",
                ]],
            ),
            "marketdata": _block(
                ["SECID", "LAST", "MARKETPRICE", "LCURRENTPRICE", "VALTODAY", "SYSTIME"],
                [[asset_id, 117.35, 122.85, 117.35, 601551768, "2026-08-14 23:50:43"]],
            ),
        },
    )


def test_provider_maps_strict_moex_facts_and_dirty_ofz_cost() -> None:
    with httpx.Client(transport=httpx.MockTransport(_handler)) as client:
        result = MoexIssProvider(client=client).discover(calculated_at=NOW)

    ofz = next(item for item in result if item.kind is InstrumentKind.OFZ)
    assert ofz.unit_price == Decimal("818.21000000")
    assert ofz.clean_price_percent == Decimal("78.445")
    assert ofz.accrued_interest == Decimal("33.76")
    assert ofz.maturity_date is not None
    assert ofz.maturity_date.isoformat() == "2031-09-17"
    assert ofz.price_as_of.tzinfo is not None
    funds = [item for item in result if item.kind is InstrumentKind.EQUITY_INDEX_FUND]
    assert {item.asset_id for item in funds} == {"EQMX", "SBMX", "TMOS"}
    assert all(item.classification_url == "https://www.moex.com/msn/etf" for item in funds)
    stocks = [item for item in result if item.kind is InstrumentKind.DIVIDEND_STOCK]
    assert [item.asset_id for item in stocks] == ["MOEX"]
    assert stocks[0].lot_size == 10
    assert stocks[0].research is not None
    assert {citation.kind.value for citation in stocks[0].research.citations} == {
        "fundamentals",
        "dividends",
        "governance",
        "corporate_actions",
    }


def test_provider_rejects_malformed_moex_block() -> None:
    def malformed(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"securities": {"columns": [], "data": []}})

    with (
        httpx.Client(transport=httpx.MockTransport(malformed)) as client,
        pytest.raises(MarketDataError) as captured,
    ):
        MoexIssProvider(client=client).discover(calculated_at=NOW)

    assert captured.value.code == "MOEX_INVALID_RESPONSE"


def test_provider_maps_transport_failure_without_fallback() -> None:
    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with (
        httpx.Client(transport=httpx.MockTransport(unavailable)) as client,
        pytest.raises(MarketDataError) as captured,
    ):
        MoexIssProvider(client=client).discover(calculated_at=NOW)

    assert captured.value.code == "MOEX_UNAVAILABLE"
