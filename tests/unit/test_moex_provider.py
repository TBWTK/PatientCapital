from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from patientcapital.marketdata.errors import MarketDataError
from patientcapital.marketdata.models import InstrumentKind
from patientcapital.marketdata.moex import MoexIssProvider
from patientcapital.research.models import ResearchScope

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def _block(columns: list[str], data: list[list[object]]) -> dict[str, object]:
    return {"columns": columns, "data": data}


def _handler(request: httpx.Request) -> httpx.Response:
    if "/history/" in request.url.path:
        session_date = request.url.params["date"]
        if "/bonds/" in request.url.path:
            history_rows = [["SU26218RMFS6", session_date, 5000, 742285912]]
        else:
            history_rows = [
                [asset_id, session_date, trades, turnover]
                for asset_id, trades, turnover in (
                    ("EQMX", 5000, 601551768),
                    ("SBMX", 4000, 501551768),
                    ("TMOS", 3000, 401551768),
                    ("SBER", 15000, 1601551768),
                    ("MOEX", 12000, 1201551768),
                    ("THIRD", 1000, 201551768),
                )
            ]
        return httpx.Response(
            200,
            json={
                "history": _block(["SECID", "TRADEDATE", "NUMTRADES", "VALUE"], history_rows),
                "history.cursor": _block(
                    ["INDEX", "TOTAL", "PAGESIZE"], [[0, len(history_rows), 100]]
                ),
            },
        )
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
                    [
                        "SECID",
                        "LAST",
                        "MARKETPRICE",
                        "YIELD",
                        "VALTODAY",
                        "BID",
                        "OFFER",
                        "SYSTIME",
                    ],
                    [
                        [
                            "SU26218RMFS6",
                            78.445,
                            78.4,
                            15.19,
                            742285912,
                            78.4,
                            78.5,
                            "2026-08-14 23:50:44",
                        ]
                    ],
                ),
            },
        )
    if request.url.path.endswith("/dividends.json"):
        asset_id = request.url.path.split("/")[-2]
        return httpx.Response(
            200,
            json={
                "dividends": _block(
                    ["secid", "registryclosedate", "value", "currencyid"],
                    [
                        [asset_id, "2025-07-18", 30, "RUB"],
                        [asset_id, "2024-07-18", 25, "RUB"],
                        [asset_id, "2023-07-18", 20, "RUB"],
                    ],
                )
            },
        )
    rows = [
        ["EQMX", "EQMX ETF", 1, "A", "SUR", "J", "IFTF", "RU000EQMX", 1],
        ["SBMX", "SBMX ETF", 1, "A", "SUR", "J", "IFTF", "RU000SBMX", 1],
        ["TMOS", "TMOS ETF", 1, "A", "SUR", "J", "IFTF", "RU000TMOS", 1],
        ["SBER", "Сбербанк", 10, "A", "SUR", "1", "EQIN", "RU000SBER", 1],
        ["MOEX", "МосБиржа", 10, "A", "SUR", "1", "EQIN", "RU000MOEX", 1],
        ["THIRD", "Третья", 10, "A", "SUR", "1", "EQIN", "RU000THIRD", 1],
    ]
    market = [
        [
            asset_id,
            117.35,
            122.85,
            117.35,
            turnover,
            117.30,
            117.40,
            "2026-08-14 23:50:43",
        ]
        for asset_id, turnover in (
            ("EQMX", 601551768),
            ("SBMX", 501551768),
            ("TMOS", 401551768),
            ("SBER", 1601551768),
            ("MOEX", 1201551768),
            ("THIRD", 201551768),
        )
    ]
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
                    "LISTLEVEL",
                ],
                rows,
            ),
            "marketdata": _block(
                [
                    "SECID",
                    "LAST",
                    "MARKETPRICE",
                    "LCURRENTPRICE",
                    "VALTODAY",
                    "BID",
                    "OFFER",
                    "SYSTIME",
                ],
                market,
            ),
        },
    )


def test_provider_maps_strict_moex_facts_and_dirty_ofz_cost() -> None:
    with httpx.Client(transport=httpx.MockTransport(_handler)) as client:
        scan = MoexIssProvider(client=client, stock_prefilter_limit=2).scan(calculated_at=NOW)
        result = scan.candidates

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
    stocks = [item for item in result if item.kind is InstrumentKind.PUBLIC_EQUITY]
    assert [item.asset_id for item in stocks] == ["SBER", "MOEX", "THIRD"]
    assert stocks[0].lot_size == 10
    assert stocks[0].research is not None
    assert stocks[0].research.scope is ResearchScope.MARKET_SCREEN
    assert stocks[0].research.dividend_years == 3
    assert stocks[0].liquidity is not None
    assert len(stocks[0].liquidity.observations) == 20
    assert stocks[2].research is None
    assert {citation.kind.value for citation in stocks[0].research.citations} == {
        "listing",
        "dividends",
    }
    assert scan.enriched_count == 2
    assert scan.universe_size == 7


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
