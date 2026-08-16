"""Fail-closed adapter for delayed public MOEX ISS market facts."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import nullcontext
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

import httpx

from patientcapital.marketdata.errors import MarketDataError
from patientcapital.marketdata.models import InstrumentKind, MarketCandidate
from patientcapital.research.corpus import MOEX_DIVIDEND_RESEARCH

_MOEX_TIMEZONE = ZoneInfo("Europe/Moscow")
_FUND_CLASSIFICATION_URL = "https://www.moex.com/msn/etf"
_APPROVED_FUNDS: Mapping[str, str] = {
    "EQMX": "ВИМ — Индекс МосБиржи",
    "SBMX": "Первая — Фонд Топ Российских акций",
    "TMOS": "Тинькофф / Т-Капитал — Индекс МосБиржи",  # noqa: RUF001
}
_APPROVED_DIVIDEND_STOCKS: Mapping[str, str] = {
    "MOEX": "Московская биржа",
}
_DIVIDEND_STOCK_CLASSIFICATION_URL = "https://www.moex.com/en/stocks/moex"
_BOND_SECURITY_COLUMNS = (
    "SECID",
    "SHORTNAME",
    "LOTSIZE",
    "STATUS",
    "FACEVALUE",
    "FACEUNIT",
    "ACCRUEDINT",
    "MATDATE",
    "COUPONPERCENT",
)
_BOND_MARKET_COLUMNS = ("SECID", "LAST", "MARKETPRICE", "YIELD", "VALTODAY", "SYSTIME")
_FUND_SECURITY_COLUMNS = (
    "SECID",
    "SHORTNAME",
    "LOTSIZE",
    "STATUS",
    "CURRENCYID",
    "SECTYPE",
    "INSTRID",
    "ISIN",
)
_FUND_MARKET_COLUMNS = (
    "SECID",
    "LAST",
    "MARKETPRICE",
    "LCURRENTPRICE",
    "VALTODAY",
    "SYSTIME",
)


def _decimal(value: object, *, field: str, positive: bool = False) -> Decimal:
    if value is None or isinstance(value, bool):
        raise MarketDataError("MOEX_INVALID_RESPONSE", f"{field} is missing")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise MarketDataError("MOEX_INVALID_RESPONSE", f"{field} is not decimal") from error
    if not result.is_finite() or (positive and result <= 0):
        raise MarketDataError("MOEX_INVALID_RESPONSE", f"{field} is outside the valid range")
    return result


def _integer(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise MarketDataError("MOEX_INVALID_RESPONSE", f"{field} is not an integer")
    try:
        result = int(str(value))
    except ValueError as error:
        raise MarketDataError("MOEX_INVALID_RESPONSE", f"{field} is not an integer") from error
    if result <= 0:
        raise MarketDataError("MOEX_INVALID_RESPONSE", f"{field} must be positive")
    return result


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise MarketDataError("MOEX_INVALID_RESPONSE", "SYSTIME is missing")
    try:
        local = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_MOEX_TIMEZONE)
    except ValueError as error:
        raise MarketDataError("MOEX_INVALID_RESPONSE", "SYSTIME has an unknown format") from error
    return local.astimezone(UTC)


def _date(value: object, *, field: str) -> date:
    if not isinstance(value, str):
        raise MarketDataError("MOEX_INVALID_RESPONSE", f"{field} is missing")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise MarketDataError("MOEX_INVALID_RESPONSE", f"{field} has an unknown format") from error


def _rows(payload: object, block_name: str) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        raise MarketDataError("MOEX_INVALID_RESPONSE", "response root must be an object")
    block = payload.get(block_name)
    if not isinstance(block, dict):
        raise MarketDataError("MOEX_INVALID_RESPONSE", f"{block_name} block is missing")
    columns = block.get("columns")
    data = block.get("data")
    if (
        not isinstance(columns, list)
        or not columns
        or not all(isinstance(item, str) for item in columns)
    ):
        raise MarketDataError("MOEX_INVALID_RESPONSE", f"{block_name}.columns is invalid")
    if not isinstance(data, list):
        raise MarketDataError("MOEX_INVALID_RESPONSE", f"{block_name}.data is invalid")
    result: list[dict[str, object]] = []
    for index, row in enumerate(data):
        if not isinstance(row, list) or len(row) != len(columns):
            raise MarketDataError(
                "MOEX_INVALID_RESPONSE", f"{block_name}.data[{index}] has invalid width"
            )
        result.append(dict(zip(columns, row, strict=True)))
    return result


def _string(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise MarketDataError("MOEX_INVALID_RESPONSE", f"{field} is missing")
    return value.strip()


class MoexIssProvider:
    """Fetch a constrained universe from official delayed MOEX ISS endpoints."""

    name = "moex-iss-delayed-v1"

    def __init__(
        self,
        *,
        base_url: str = "https://iss.moex.com/iss",
        timeout_seconds: float = 10.0,
        max_age_seconds: int = 345_600,
        client: httpx.Client | None = None,
    ) -> None:
        if base_url.rstrip("/") != "https://iss.moex.com/iss":
            raise ValueError("MOEX ISS base URL must remain allowlisted")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_age = timedelta(seconds=max_age_seconds)
        self._client = client

    def _get(self, client: httpx.Client, path: str, params: dict[str, str]) -> object:
        try:
            response = client.get(f"{self._base_url}{path}", params=params, timeout=self._timeout)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise MarketDataError(
                "MOEX_UNAVAILABLE", "MOEX ISS request failed; automatic proposal was not created"
            ) from error

    def _bond_candidates(self, client: httpx.Client) -> list[MarketCandidate]:
        path = "/engines/stock/markets/bonds/boards/TQOB/securities.json"
        payload = self._get(
            client,
            path,
            {
                "iss.meta": "off",
                "iss.only": "securities,marketdata",
                "securities.columns": ",".join(_BOND_SECURITY_COLUMNS),
                "marketdata.columns": ",".join(_BOND_MARKET_COLUMNS),
                "limit": "100",
            },
        )
        securities = _rows(payload, "securities")
        market = {_string(row, "SECID"): row for row in _rows(payload, "marketdata")}
        candidates: list[MarketCandidate] = []
        for security in securities:
            if security.get("STATUS") != "A" or security.get("FACEUNIT") not in {"SUR", "RUB"}:
                continue
            asset_id = _string(security, "SECID")
            quote = market.get(asset_id)
            if quote is None or (quote.get("LAST") is None and quote.get("MARKETPRICE") is None):
                continue
            clean_field = "LAST" if quote.get("LAST") is not None else "MARKETPRICE"
            clean = _decimal(quote.get(clean_field), field=clean_field, positive=True)
            face = _decimal(security.get("FACEVALUE"), field="FACEVALUE", positive=True)
            accrued = _decimal(security.get("ACCRUEDINT"), field="ACCRUEDINT")
            if accrued < 0:
                raise MarketDataError("MOEX_INVALID_RESPONSE", "ACCRUEDINT cannot be negative")
            dirty = (face * clean / Decimal("100") + accrued).quantize(Decimal("0.00000001"))
            candidates.append(
                MarketCandidate(
                    asset_id=asset_id,
                    name=_string(security, "SHORTNAME"),
                    kind=InstrumentKind.OFZ,
                    currency="RUB",
                    lot_size=_integer(security.get("LOTSIZE"), field="LOTSIZE"),
                    unit_price=dirty,
                    price_as_of=_timestamp(quote.get("SYSTIME")),
                    max_age=self._max_age,
                    source_url=f"{self._base_url}{path.removesuffix('.json')}/{asset_id}.json",
                    classification_url="https://www.moex.com/ru/marketdata/",
                    quote_kind=f"{clean_field.lower()}_dirty",
                    turnover=_decimal(quote.get("VALTODAY") or 0, field="VALTODAY"),
                    maturity_date=_date(security.get("MATDATE"), field="MATDATE"),
                    yield_percent=(
                        _decimal(quote.get("YIELD"), field="YIELD")
                        if quote.get("YIELD") is not None
                        else None
                    ),
                    clean_price_percent=clean,
                    face_value=face,
                    accrued_interest=accrued,
                )
            )
        return candidates

    def _fund_candidate(self, client: httpx.Client, asset_id: str) -> MarketCandidate:
        path = f"/engines/stock/markets/shares/boards/TQBR/securities/{asset_id}.json"
        payload = self._get(
            client,
            path,
            {
                "iss.meta": "off",
                "iss.only": "securities,marketdata",
                "securities.columns": ",".join(_FUND_SECURITY_COLUMNS),
                "marketdata.columns": ",".join(_FUND_MARKET_COLUMNS),
            },
        )
        securities = _rows(payload, "securities")
        markets = _rows(payload, "marketdata")
        if len(securities) != 1 or len(markets) != 1:
            raise MarketDataError(
                "MOEX_INSTRUMENT_UNAVAILABLE", f"approved fund {asset_id} is not tradeable"
            )
        security = securities[0]
        quote = markets[0]
        if (
            _string(security, "SECID") != asset_id
            or _string(quote, "SECID") != asset_id
            or security.get("STATUS") != "A"
            or security.get("CURRENCYID") not in {"SUR", "RUB"}
            or security.get("SECTYPE") != "J"
            or security.get("INSTRID") != "IFTF"
        ):
            raise MarketDataError(
                "MOEX_INSTRUMENT_UNAVAILABLE", f"approved fund {asset_id} changed classification"
            )
        price_field = next(
            (
                field
                for field in ("LCURRENTPRICE", "LAST", "MARKETPRICE")
                if quote.get(field) is not None
            ),
            None,
        )
        if price_field is None:
            raise MarketDataError(
                "MOEX_INSTRUMENT_UNAVAILABLE", f"approved fund {asset_id} has no price"
            )
        return MarketCandidate(
            asset_id=asset_id,
            name=_APPROVED_FUNDS[asset_id],
            kind=InstrumentKind.EQUITY_INDEX_FUND,
            currency="RUB",
            lot_size=_integer(security.get("LOTSIZE"), field="LOTSIZE"),
            unit_price=_decimal(quote.get(price_field), field=price_field, positive=True).quantize(
                Decimal("0.00000001")
            ),
            price_as_of=_timestamp(quote.get("SYSTIME")),
            max_age=self._max_age,
            source_url=f"{self._base_url}{path}",
            classification_url=_FUND_CLASSIFICATION_URL,
            quote_kind=price_field.lower(),
            turnover=_decimal(quote.get("VALTODAY") or 0, field="VALTODAY"),
        )

    def _dividend_stock_candidate(self, client: httpx.Client, asset_id: str) -> MarketCandidate:
        path = f"/engines/stock/markets/shares/boards/TQBR/securities/{asset_id}.json"
        payload = self._get(
            client,
            path,
            {
                "iss.meta": "off",
                "iss.only": "securities,marketdata",
                "securities.columns": ",".join(_FUND_SECURITY_COLUMNS),
                "marketdata.columns": ",".join(_FUND_MARKET_COLUMNS),
            },
        )
        securities = _rows(payload, "securities")
        markets = _rows(payload, "marketdata")
        if len(securities) != 1 or len(markets) != 1:
            raise MarketDataError(
                "MOEX_INSTRUMENT_UNAVAILABLE",
                f"approved dividend stock {asset_id} is not tradeable",
            )
        security = securities[0]
        quote = markets[0]
        if (
            _string(security, "SECID") != asset_id
            or _string(quote, "SECID") != asset_id
            or security.get("STATUS") != "A"
            or security.get("CURRENCYID") not in {"SUR", "RUB"}
            or security.get("SECTYPE") != "1"
            or security.get("INSTRID") != "EQIN"
            or security.get("ISIN") != "RU000A0JR4A1"
        ):
            raise MarketDataError(
                "MOEX_INSTRUMENT_UNAVAILABLE",
                f"approved dividend stock {asset_id} changed classification",
            )
        price_field = next(
            (
                field
                for field in ("LCURRENTPRICE", "LAST", "MARKETPRICE")
                if quote.get(field) is not None
            ),
            None,
        )
        if price_field is None:
            raise MarketDataError(
                "MOEX_INSTRUMENT_UNAVAILABLE", f"approved dividend stock {asset_id} has no price"
            )
        return MarketCandidate(
            asset_id=asset_id,
            name=_APPROVED_DIVIDEND_STOCKS[asset_id],
            kind=InstrumentKind.DIVIDEND_STOCK,
            currency="RUB",
            lot_size=_integer(security.get("LOTSIZE"), field="LOTSIZE"),
            unit_price=_decimal(quote.get(price_field), field=price_field, positive=True).quantize(
                Decimal("0.00000001")
            ),
            price_as_of=_timestamp(quote.get("SYSTIME")),
            max_age=self._max_age,
            source_url=f"{self._base_url}{path}",
            classification_url=_DIVIDEND_STOCK_CLASSIFICATION_URL,
            quote_kind=price_field.lower(),
            turnover=_decimal(quote.get("VALTODAY") or 0, field="VALTODAY"),
            research=MOEX_DIVIDEND_RESEARCH,
        )

    def discover(self, *, calculated_at: datetime) -> tuple[MarketCandidate, ...]:
        if calculated_at.tzinfo is None or calculated_at.utcoffset() is None:
            raise MarketDataError("INVALID_CALCULATION_TIME", "calculated_at must include timezone")
        manager = (
            nullcontext(self._client)
            if self._client is not None
            else httpx.Client(headers={"User-Agent": "PatientCapital/0.1"})
        )
        with manager as client:
            if client is None:  # pragma: no cover - nullcontext preserves injected client
                raise RuntimeError("HTTP client is unavailable")
            candidates = self._bond_candidates(client)
            candidates.extend(self._fund_candidate(client, item) for item in _APPROVED_FUNDS)
            candidates.extend(
                self._dividend_stock_candidate(client, item)
                for item in _APPROVED_DIVIDEND_STOCKS
            )
        if not candidates:
            raise MarketDataError("MOEX_NO_CANDIDATES", "MOEX returned no validated candidates")
        return tuple(candidates)


__all__ = ["MoexIssProvider"]
