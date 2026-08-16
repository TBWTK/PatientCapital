from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from patientcapital.api.app import create_app
from patientcapital.config import Settings
from patientcapital.domain.errors import InvalidAllocationInput
from patientcapital.market_intelligence.service import acquire_market_research
from patientcapital.marketdata.errors import MarketDataError
from patientcapital.marketdata.models import InstrumentKind, MarketCandidate, MarketScan
from patientcapital.persistence.database import Database
from tests.integration.conftest import TEST_DATABASE_URL


class CountingScanner:
    name = "counting-market-scanner"

    def __init__(self) -> None:
        self.calls = 0

    def scan(self, *, calculated_at: datetime) -> MarketScan:
        self.calls += 1
        candidate = MarketCandidate(
            asset_id="DYNAMIC-OFZ",
            name="Динамическая ОФЗ",
            kind=InstrumentKind.OFZ,
            currency="RUB",
            lot_size=1,
            unit_price=Decimal("800"),
            price_as_of=calculated_at - timedelta(minutes=5),
            max_age=timedelta(days=4),
            source_url="https://iss.moex.com/dynamic-ofz",
            classification_url="https://www.moex.com/ru/marketdata/",
            quote_kind="last_dirty",
            turnover=Decimal("500000000"),
            maturity_date=calculated_at.date().replace(year=calculated_at.year + 5),
            yield_percent=Decimal("15.50"),
            clean_price_percent=Decimal("78"),
            face_value=Decimal("1000"),
            accrued_interest=Decimal("20"),
            next_coupon_date=calculated_at.date() + timedelta(days=60),
            coupon_percent=Decimal("12"),
        )
        return MarketScan(
            policy_version="moex-board-scan-v1",
            observed_at=calculated_at,
            candidates=(candidate,),
            universe_size=321,
            kind_counts={"ofz": 54, "equity_index_fund": 3, "dividend_stock": 12},
            enriched_count=12,
        )

    def discover(self, *, calculated_at: datetime) -> tuple[MarketCandidate, ...]:
        return self.scan(calculated_at=calculated_at).candidates


class FailingScanner:
    name = "failing-market-scanner"

    def scan(self, *, calculated_at: datetime) -> MarketScan:
        del calculated_at
        raise MarketDataError("MOEX_INVALID_RESPONSE", "required board data is incomplete")

    def discover(self, *, calculated_at: datetime) -> tuple[MarketCandidate, ...]:
        return self.scan(calculated_at=calculated_at).candidates


def _configure_profile(client: TestClient) -> None:
    response = client.put(
        "/v1/profile",
        json={
            "expected_version": None,
            "base_currency": "RUB",
            "investment_horizon_years": 5,
            "risk_level": "growth",
            "cash_buffer": "0.00",
            "broker_name": "T-Investments",
            "fee_rate": "0.0005",
            "minimum_fee": "0.00",
        },
    )
    assert response.status_code == 200


def test_proposal_persists_and_reuses_fresh_market_snapshot_without_trading() -> None:
    scanner = CountingScanner()
    settings = Settings(
        database_url=TEST_DATABASE_URL,
        app_env="test",
        market_research_cache_seconds=14_400,
    )
    with TestClient(create_app(settings, market_data_provider=scanner)) as client:
        _configure_profile(client)

        first = client.post("/v1/proposal-sets", json={"contribution": "8000.00"})
        second = client.post("/v1/proposal-sets", json={"contribution": "50000.00"})

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    first_search = first.json()["strategies"][0]["recommendation"]["search"]
    second_search = second.json()["strategies"][0]["recommendation"]["search"]
    assert first_search["mode"] == "live"
    assert second_search["mode"] == "cached"
    assert first_search["snapshot_id"] == second_search["snapshot_id"]
    assert first_search["universe_size"] == 321
    assert first_search["kind_counts"]["ofz"] == 54
    assert scanner.calls == 1

    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM market_research_snapshots")) == 1
        assert connection.scalar(text("SELECT count(*) FROM transactions")) == 0
    engine.dispose()


def test_latest_market_research_endpoint_exposes_snapshot_status() -> None:
    scanner = CountingScanner()
    settings = Settings(database_url=TEST_DATABASE_URL, app_env="test")
    with TestClient(create_app(settings, market_data_provider=scanner)) as client:
        _configure_profile(client)
        created = client.post("/v1/proposal-sets", json={"contribution": "8000.00"})
        latest = client.get("/v1/market-research/latest")

    assert created.status_code == 201
    assert latest.status_code == 200
    payload = latest.json()
    assert payload["status"] == "succeeded"
    assert payload["provider"] == scanner.name
    assert payload["universe_size"] == 321
    assert datetime.fromisoformat(payload["observed_at"]).tzinfo is not None


def test_provider_failure_is_persisted_and_never_hidden_by_an_old_universe() -> None:
    settings = Settings(database_url=TEST_DATABASE_URL, app_env="test")
    with TestClient(create_app(settings, market_data_provider=FailingScanner())) as client:
        _configure_profile(client)
        failed = client.post("/v1/proposal-sets", json={"contribution": "8000.00"})
        latest = client.get("/v1/market-research/latest")

    assert failed.status_code == 502
    assert failed.json()["error"]["code"] == "MOEX_INVALID_RESPONSE"
    assert latest.status_code == 200
    assert latest.json()["status"] == "provider_error"
    assert latest.json()["error_code"] == "MOEX_INVALID_RESPONSE"
    assert latest.json()["candidate_count"] == 0


def test_missing_snapshot_and_invalid_acquisition_inputs_remain_explicit() -> None:
    settings = Settings(database_url=TEST_DATABASE_URL, app_env="test")
    with TestClient(create_app(settings, market_data_provider=CountingScanner())) as client:
        missing = client.get("/v1/market-research/latest")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "MARKET_RESEARCH_NOT_FOUND"

    database = Database(TEST_DATABASE_URL)
    try:
        with database.sessions() as session:
            with pytest.raises(InvalidAllocationInput, match="timezone-aware"):
                acquire_market_research(
                    session,
                    CountingScanner(),
                    observed_at=datetime(2026, 8, 16, 10, 0),
                    cache_seconds=14_400,
                )
            with pytest.raises(InvalidAllocationInput, match="cache must be positive"):
                acquire_market_research(
                    session,
                    CountingScanner(),
                    observed_at=datetime.fromisoformat("2026-08-16T10:00:00+00:00"),
                    cache_seconds=0,
                )
    finally:
        database.close()


def test_failed_snapshot_idempotency_never_retries_with_a_different_provider() -> None:
    observed_at = datetime.fromisoformat("2026-08-16T10:00:00+00:00")
    database = Database(TEST_DATABASE_URL)
    replacement = CountingScanner()
    try:
        with (
            database.sessions() as session,
            pytest.raises(MarketDataError, match="required board data"),
        ):
            acquire_market_research(
                session,
                FailingScanner(),
                observed_at=observed_at,
                cache_seconds=14_400,
                force=True,
                idempotency_key="market-slot:2026-08-16T10:00:00Z",
            )
        with (
            database.sessions() as session,
            pytest.raises(MarketDataError, match="required board data"),
        ):
            acquire_market_research(
                session,
                replacement,
                observed_at=observed_at,
                cache_seconds=14_400,
                force=True,
                idempotency_key="market-slot:2026-08-16T10:00:00Z",
            )
    finally:
        database.close()
    assert replacement.calls == 0
