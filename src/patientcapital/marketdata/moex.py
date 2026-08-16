"""Fail-closed adapter for delayed public MOEX ISS market facts."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from contextlib import nullcontext
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

import httpx

from patientcapital.marketdata.errors import MarketDataError
from patientcapital.marketdata.models import (
    InstrumentKind,
    LiquidityObservation,
    MarketCandidate,
    MarketLiquidityEvidence,
    MarketScan,
)
from patientcapital.research.models import (
    BalanceSheetStatus,
    CorporateActionStatus,
    DividendResearchEvidence,
    ResearchCitation,
    ResearchFactKind,
    ResearchScope,
)

_MOEX_TIMEZONE = ZoneInfo("Europe/Moscow")
_FUND_CLASSIFICATION_URL = "https://www.moex.com/msn/etf"
_APPROVED_FUNDS: Mapping[str, str] = {
    "EQMX": "ВИМ — Индекс МосБиржи",
    "SBMX": "Первая — Фонд Топ Российских акций",
    "TMOS": "Тинькофф / Т-Капитал — Индекс МосБиржи",  # noqa: RUF001
}
_SCAN_POLICY_VERSION = "moex-board-scan-v4"
_LIQUIDITY_POLICY_VERSION = "market-liquidity-v2"
_DIVIDEND_MARKET_POLICY_VERSION = "dividend-market-screen-v1"
_DEFAULT_STOCK_PREFILTER_LIMIT = 12
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
    "NEXTCOUPON",
    "COUPONVALUE",
)
_BOND_MARKET_COLUMNS = (
    "SECID",
    "LAST",
    "MARKETPRICE",
    "YIELD",
    "VALTODAY",
    "BID",
    "OFFER",
    "SYSTIME",
)
_FUND_SECURITY_COLUMNS = (
    "SECID",
    "SHORTNAME",
    "LOTSIZE",
    "STATUS",
    "CURRENCYID",
    "SECTYPE",
    "INSTRID",
    "ISIN",
    "LISTLEVEL",
)
_FUND_MARKET_COLUMNS = (
    "SECID",
    "LAST",
    "MARKETPRICE",
    "LCURRENTPRICE",
    "VALTODAY",
    "BID",
    "OFFER",
    "SYSTIME",
)
_HISTORY_COLUMNS = ("SECID", "TRADEDATE", "NUMTRADES", "VALUE")
_ROLLING_SESSIONS = 20
_MAX_CALENDAR_LOOKBACK = 45


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

    name = "moex-market-intelligence-v1"
    scan_policy_version = _SCAN_POLICY_VERSION

    def __init__(
        self,
        *,
        base_url: str = "https://iss.moex.com/iss",
        timeout_seconds: float = 10.0,
        max_age_seconds: int = 345_600,
        stock_prefilter_limit: int = _DEFAULT_STOCK_PREFILTER_LIMIT,
        client: httpx.Client | None = None,
    ) -> None:
        if base_url.rstrip("/") != "https://iss.moex.com/iss":
            raise ValueError("MOEX ISS base URL must remain allowlisted")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_age = timedelta(seconds=max_age_seconds)
        if not 1 <= stock_prefilter_limit <= 50:
            raise ValueError("stock prefilter limit must be between 1 and 50")
        self._stock_prefilter_limit = stock_prefilter_limit
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

    def _history_page(
        self,
        client: httpx.Client,
        *,
        market: str,
        board: str,
        session_date: date,
        start: int,
    ) -> tuple[list[dict[str, object]], int, int]:
        payload = self._get(
            client,
            f"/history/engines/stock/markets/{market}/boards/{board}/securities.json",
            {
                "iss.meta": "off",
                "iss.only": "history,history.cursor",
                "history.columns": ",".join(_HISTORY_COLUMNS),
                "date": session_date.isoformat(),
                "limit": "100",
                "start": str(start),
            },
        )
        rows = _rows(payload, "history")
        cursor = _rows(payload, "history.cursor")
        if len(cursor) != 1:
            raise MarketDataError("MOEX_INVALID_RESPONSE", "history.cursor must contain one row")
        total_value = cursor[0].get("TOTAL")
        page_size_value = cursor[0].get("PAGESIZE")
        if isinstance(total_value, bool) or isinstance(page_size_value, bool):
            raise MarketDataError("MOEX_INVALID_RESPONSE", "history cursor is invalid")
        try:
            total = int(str(total_value))
            page_size = int(str(page_size_value))
        except ValueError as error:
            raise MarketDataError("MOEX_INVALID_RESPONSE", "history cursor is invalid") from error
        if total < 0 or page_size <= 0:
            raise MarketDataError("MOEX_INVALID_RESPONSE", "history cursor is invalid")
        return rows, total, page_size

    def _rolling_history(
        self,
        client: httpx.Client,
        *,
        market: str,
        board: str,
        calculated_at: datetime,
    ) -> dict[str, tuple[LiquidityObservation, ...]]:
        by_asset: dict[str, list[LiquidityObservation]] = defaultdict(list)
        completed_sessions = 0
        calendar_offset = 1
        while completed_sessions < _ROLLING_SESSIONS and calendar_offset <= _MAX_CALENDAR_LOOKBACK:
            session_date = calculated_at.date() - timedelta(days=calendar_offset)
            first, total, page_size = self._history_page(
                client,
                market=market,
                board=board,
                session_date=session_date,
                start=0,
            )
            rows = list(first)
            start = page_size
            while start < total:
                page, _, next_page_size = self._history_page(
                    client,
                    market=market,
                    board=board,
                    session_date=session_date,
                    start=start,
                )
                rows.extend(page)
                start += next_page_size
            if rows:
                dates = {_date(row.get("TRADEDATE"), field="TRADEDATE") for row in rows}
                if dates != {session_date}:
                    raise MarketDataError(
                        "MOEX_INVALID_RESPONSE", "history rows do not match requested session"
                    )
                completed_sessions += 1
                for row in rows:
                    asset_id = _string(row, "SECID")
                    trades_raw = row.get("NUMTRADES")
                    if isinstance(trades_raw, bool):
                        raise MarketDataError("MOEX_INVALID_RESPONSE", "NUMTRADES is invalid")
                    try:
                        trades = int(str(trades_raw))
                    except ValueError as error:
                        raise MarketDataError(
                            "MOEX_INVALID_RESPONSE", "NUMTRADES is invalid"
                        ) from error
                    if trades < 0:
                        raise MarketDataError("MOEX_INVALID_RESPONSE", "NUMTRADES is invalid")
                    turnover = _decimal(row.get("VALUE") or 0, field="VALUE")
                    by_asset[asset_id].append(
                        LiquidityObservation(
                            session_date=session_date,
                            turnover_rub=turnover,
                            trades=trades,
                        )
                    )
            calendar_offset += 1
        if completed_sessions == 0:
            raise MarketDataError(
                "MOEX_NO_LIQUIDITY_HISTORY", "MOEX returned no completed-session history"
            )
        return {asset_id: tuple(items) for asset_id, items in by_asset.items()}

    def _liquidity_evidence(
        self,
        *,
        asset_id: str,
        status: object,
        quote: Mapping[str, object],
        history: Mapping[str, tuple[LiquidityObservation, ...]],
        observed_at: datetime,
        history_url: str,
    ) -> MarketLiquidityEvidence | None:
        observations = list(history.get(asset_id, ()))
        if not observations:
            return None
        bid = (
            _decimal(quote.get("BID"), field="BID", positive=True)
            if quote.get("BID") is not None
            else None
        )
        offer = (
            _decimal(quote.get("OFFER"), field="OFFER", positive=True)
            if quote.get("OFFER") is not None
            else None
        )
        if (bid is None) != (offer is None):
            bid = None
            offer = None
        if bid is not None and offer is not None:
            first = observations[0]
            observations[0] = LiquidityObservation(
                session_date=first.session_date,
                turnover_rub=first.turnover_rub,
                trades=first.trades,
                bid=bid,
                offer=offer,
            )
        return MarketLiquidityEvidence(
            policy_version=_LIQUIDITY_POLICY_VERSION,
            observed_at=observed_at,
            max_age=self._max_age,
            security_status="active" if status == "A" else "unknown",
            observations=tuple(observations),
            source_url=history_url,
        )

    def _bond_candidates(
        self,
        client: httpx.Client,
        *,
        history: Mapping[str, tuple[LiquidityObservation, ...]],
        calculated_at: datetime,
    ) -> list[MarketCandidate]:
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
            if not asset_id.startswith("SU262"):
                continue
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
                    next_coupon_date=(
                        _date(security.get("NEXTCOUPON"), field="NEXTCOUPON")
                        if security.get("NEXTCOUPON") is not None
                        else None
                    ),
                    coupon_percent=(
                        _decimal(security.get("COUPONPERCENT"), field="COUPONPERCENT")
                        if security.get("COUPONPERCENT") is not None
                        else None
                    ),
                    coupon_value=(
                        _decimal(security.get("COUPONVALUE"), field="COUPONVALUE")
                        if security.get("COUPONVALUE") is not None
                        else None
                    ),
                    liquidity=self._liquidity_evidence(
                        asset_id=asset_id,
                        status=security.get("STATUS"),
                        quote=quote,
                        history=history,
                        observed_at=calculated_at,
                        history_url=(
                            f"{self._base_url}/history/engines/stock/markets/bonds/"
                            f"boards/TQOB/securities/{asset_id}.json"
                        ),
                    ),
                )
            )
        return candidates

    @staticmethod
    def _price_field(quote: Mapping[str, object]) -> str | None:
        return next(
            (
                field
                for field in ("LCURRENTPRICE", "LAST", "MARKETPRICE")
                if quote.get(field) is not None
            ),
            None,
        )

    def _dividend_research(
        self,
        client: httpx.Client,
        *,
        asset_id: str,
        listing_level: int,
        unit_price: Decimal,
        calculated_at: datetime,
    ) -> DividendResearchEvidence:
        path = f"/securities/{asset_id}/dividends.json"
        payload = self._get(
            client,
            path,
            {
                "iss.meta": "off",
                "iss.only": "dividends",
                "dividends.columns": "secid,registryclosedate,value,currencyid",
            },
        )
        valid: list[tuple[date, Decimal]] = []
        for row in _rows(payload, "dividends"):
            if row.get("currencyid") not in {"RUB", "SUR"}:
                continue
            closed = _date(row.get("registryclosedate"), field="registryclosedate")
            if closed > calculated_at.date():
                continue
            value = _decimal(row.get("value"), field="value")
            if value > 0:
                valid.append((closed, value))
        valid.sort(key=lambda item: item[0])
        if valid:
            latest_year = valid[-1][0].year
            annual = sum(
                (value for closed, value in valid if closed.year == latest_year), Decimal("0")
            )
            years = {
                closed.year
                for closed, _ in valid
                if calculated_at.year - 4 <= closed.year <= calculated_at.year
            }
            last_registry = valid[-1][0]
        else:
            annual = Decimal("0")
            years = set()
            last_registry = None
        historical_yield = (annual / unit_price * Decimal("100")).quantize(Decimal("0.00000001"))
        listing_url = (
            f"{self._base_url}/engines/stock/markets/shares/boards/TQBR/securities/{asset_id}.json"
        )
        return DividendResearchEvidence(
            schema_version="dividend-market-evidence-v1",
            policy_version=_DIVIDEND_MARKET_POLICY_VERSION,
            observed_at=calculated_at,
            max_age=self._max_age,
            reporting_period_end=last_registry,
            profitable_years=None,
            dividend_years=len(years),
            payout_ratio_percent=None,
            balance_sheet_status=BalanceSheetStatus.UNKNOWN,
            governance_program_member=None,
            corporate_action_status=CorporateActionStatus.UNKNOWN,
            summary=(
                f"MOEX market screen: выплаты найдены в {len(years)} из пяти последних "
                f"наблюдаемых лет; выплата за последний год истории {annual}. "
                "Profitability, payout, balance, governance и corporate actions не проверены."
            ),
            citations=(
                ResearchCitation(
                    kind=ResearchFactKind.LISTING,
                    title=f"MOEX TQBR listing {asset_id}",
                    url=listing_url,
                ),
                ResearchCitation(
                    kind=ResearchFactKind.DIVIDENDS,
                    title=f"MOEX dividend history {asset_id}",
                    url=f"{self._base_url}{path}",
                ),
            ),
            scope=ResearchScope.MARKET_SCREEN,
            annual_dividend_per_share=annual,
            historical_dividend_yield_percent=historical_yield,
            last_registry_close_date=last_registry,
            listing_level=listing_level,
            unknown_facts=(
                "profitability",
                "payout",
                "balance",
                "governance",
                "corporate_actions",
            ),
        )

    def _share_candidates(
        self,
        client: httpx.Client,
        *,
        calculated_at: datetime,
        history: Mapping[str, tuple[LiquidityObservation, ...]],
    ) -> tuple[list[MarketCandidate], int, int]:
        path = "/engines/stock/markets/shares/boards/TQBR/securities.json"
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
        markets = {_string(row, "SECID"): row for row in _rows(payload, "marketdata")}
        funds: list[MarketCandidate] = []
        stock_rows: list[tuple[Decimal, str, Mapping[str, object], Mapping[str, object]]] = []
        for security in securities:
            asset_id = _string(security, "SECID")
            quote = markets.get(asset_id)
            if (
                quote is None
                or security.get("STATUS") != "A"
                or security.get("CURRENCYID") not in {"SUR", "RUB"}
            ):
                continue
            price_field = self._price_field(quote)
            if price_field is None:
                continue
            turnover = _decimal(quote.get("VALTODAY") or 0, field="VALTODAY")
            if (
                asset_id in _APPROVED_FUNDS
                and security.get("SECTYPE") == "J"
                and security.get("INSTRID") == "IFTF"
            ):
                funds.append(
                    MarketCandidate(
                        asset_id=asset_id,
                        name=_APPROVED_FUNDS[asset_id],
                        kind=InstrumentKind.EQUITY_INDEX_FUND,
                        currency="RUB",
                        lot_size=_integer(security.get("LOTSIZE"), field="LOTSIZE"),
                        unit_price=_decimal(
                            quote.get(price_field), field=price_field, positive=True
                        ).quantize(Decimal("0.00000001")),
                        price_as_of=_timestamp(quote.get("SYSTIME")),
                        max_age=self._max_age,
                        source_url=f"{self._base_url}{path.removesuffix('.json')}/{asset_id}.json",
                        classification_url=_FUND_CLASSIFICATION_URL,
                        quote_kind=price_field.lower(),
                        turnover=turnover,
                        liquidity=self._liquidity_evidence(
                            asset_id=asset_id,
                            status=security.get("STATUS"),
                            quote=quote,
                            history=history,
                            observed_at=calculated_at,
                            history_url=(
                                f"{self._base_url}/history/engines/stock/markets/shares/"
                                f"boards/TQBR/securities/{asset_id}.json"
                            ),
                        ),
                    )
                )
                continue
            if security.get("INSTRID") != "EQIN" or security.get("SECTYPE") not in {"1", "2"}:
                continue
            listing_level = _integer(security.get("LISTLEVEL"), field="LISTLEVEL")
            if listing_level not in {1, 2}:
                continue
            stock_rows.append((turnover, asset_id, security, quote))
        rolling_rows: list[tuple[Decimal, str, Mapping[str, object], Mapping[str, object]]] = []
        for row in stock_rows:
            _, asset_id, _, _ = row
            observations = history.get(asset_id, ())
            if len(observations) < 20:
                continue
            traded = sum(item.trades > 0 for item in observations)
            turnovers = sorted(item.turnover_rub for item in observations)
            median = (turnovers[9] + turnovers[10]) / Decimal("2")
            if traded >= 15 and median >= Decimal("10000000"):
                rolling_rows.append((median, asset_id, row[2], row[3]))
        selected_ids = {
            item[1]
            for item in sorted(rolling_rows, key=lambda item: (-item[0], item[1]))[
                : self._stock_prefilter_limit
            ]
        }
        stocks: list[MarketCandidate] = []
        for turnover, asset_id, security_row, quote_row in stock_rows:
            price_field = self._price_field(quote_row)
            if price_field is None:  # guarded above
                continue
            unit_price = _decimal(
                quote_row.get(price_field), field=price_field, positive=True
            ).quantize(Decimal("0.00000001"))
            listing_level = _integer(security_row.get("LISTLEVEL"), field="LISTLEVEL")
            research = (
                self._dividend_research(
                    client,
                    asset_id=asset_id,
                    listing_level=listing_level,
                    unit_price=unit_price,
                    calculated_at=calculated_at,
                )
                if asset_id in selected_ids
                else None
            )
            stocks.append(
                MarketCandidate(
                    asset_id=asset_id,
                    name=_string(security_row, "SHORTNAME"),
                    kind=InstrumentKind.PUBLIC_EQUITY,
                    currency="RUB",
                    lot_size=_integer(security_row.get("LOTSIZE"), field="LOTSIZE"),
                    unit_price=unit_price,
                    price_as_of=_timestamp(quote_row.get("SYSTIME")),
                    max_age=self._max_age,
                    source_url=(f"{self._base_url}{path.removesuffix('.json')}/{asset_id}.json"),
                    classification_url="https://www.moex.com/ru/marketdata/",
                    quote_kind=price_field.lower(),
                    turnover=turnover,
                    isin=(
                        _string(security_row, "ISIN")
                        if security_row.get("ISIN") is not None
                        else None
                    ),
                    research=research,
                    liquidity=self._liquidity_evidence(
                        asset_id=asset_id,
                        status=security_row.get("STATUS"),
                        quote=quote_row,
                        history=history,
                        observed_at=calculated_at,
                        history_url=(
                            f"{self._base_url}/history/engines/stock/markets/shares/"
                            f"boards/TQBR/securities/{asset_id}.json"
                        ),
                    ),
                )
            )
        return funds + stocks, len(securities), len(selected_ids)

    def scan(self, *, calculated_at: datetime) -> MarketScan:
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
            bond_history = self._rolling_history(
                client,
                market="bonds",
                board="TQOB",
                calculated_at=calculated_at,
            )
            share_history = self._rolling_history(
                client,
                market="shares",
                board="TQBR",
                calculated_at=calculated_at,
            )
            bonds = self._bond_candidates(
                client,
                history=bond_history,
                calculated_at=calculated_at,
            )
            shares, share_universe_size, enriched_count = self._share_candidates(
                client,
                calculated_at=calculated_at,
                history=share_history,
            )
            candidates = bonds + shares
        if not candidates:
            raise MarketDataError("MOEX_NO_CANDIDATES", "MOEX returned no validated candidates")
        return MarketScan(
            policy_version=_SCAN_POLICY_VERSION,
            observed_at=calculated_at,
            candidates=tuple(candidates),
            universe_size=len(bonds) + share_universe_size,
            kind_counts={
                kind.value: sum(1 for item in candidates if item.kind is kind)
                for kind in InstrumentKind
            },
            enriched_count=enriched_count,
        )

    def discover(self, *, calculated_at: datetime) -> tuple[MarketCandidate, ...]:
        return self.scan(calculated_at=calculated_at).candidates


__all__ = ["MoexIssProvider"]
