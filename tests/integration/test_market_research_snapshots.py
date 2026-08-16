from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from patientcapital.api.app import create_app
from patientcapital.config import Settings
from patientcapital.domain.errors import InvalidAllocationInput
from patientcapital.market_intelligence.service import acquire_market_research
from patientcapital.marketdata.errors import MarketDataError
from patientcapital.marketdata.models import InstrumentKind, MarketCandidate, MarketScan
from patientcapital.persistence.database import Database
from patientcapital.research.corpus import MOEX_ISSUER_EVIDENCE_V2
from patientcapital.research.provider import ReviewedIssuerCorpusProvider
from tests.integration.conftest import TEST_DATABASE_URL
from tests.market_fixtures import admitted_liquidity


class CountingScanner:
    name = "counting-market-scanner"
    scan_policy_version = "moex-board-scan-v4"

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
            liquidity=admitted_liquidity(
                InstrumentKind.OFZ,
                observed_at=calculated_at - timedelta(minutes=5),
            ),
        )
        return MarketScan(
            policy_version=self.scan_policy_version,
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
    scan_policy_version = "moex-board-scan-v4"

    def scan(self, *, calculated_at: datetime) -> MarketScan:
        del calculated_at
        raise MarketDataError("MOEX_INVALID_RESPONSE", "required board data is incomplete")

    def discover(self, *, calculated_at: datetime) -> tuple[MarketCandidate, ...]:
        return self.scan(calculated_at=calculated_at).candidates


class EquityScanner:
    name = "equity-market-scanner"
    scan_policy_version = "equity-test-scan-v1"

    def scan(self, *, calculated_at: datetime) -> MarketScan:
        candidate = MarketCandidate(
            asset_id="MOEX",
            isin="RU000A0JR4A1",
            name="Moscow Exchange",
            kind=InstrumentKind.PUBLIC_EQUITY,
            currency="RUB",
            lot_size=10,
            unit_price=Decimal("180"),
            price_as_of=calculated_at - timedelta(minutes=5),
            max_age=timedelta(days=4),
            source_url="https://iss.moex.com/moex",
            classification_url="https://www.moex.com/ru/marketdata/",
            quote_kind="last",
            turnover=Decimal("100000000"),
            liquidity=admitted_liquidity(
                InstrumentKind.PUBLIC_EQUITY,
                observed_at=calculated_at - timedelta(minutes=5),
            ),
        )
        return MarketScan(
            policy_version=self.scan_policy_version,
            observed_at=calculated_at,
            candidates=(candidate,),
            universe_size=1,
            kind_counts={"public_equity": 1},
            enriched_count=0,
        )

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
        assert connection.scalar(text("SELECT count(*) FROM asset_admission_runs")) == 1
        assert connection.scalar(text("SELECT count(*) FROM asset_admission_assessments")) == 1
        assert connection.scalar(text("SELECT count(*) FROM transactions")) == 0
    engine.dispose()


def test_latest_market_research_endpoint_exposes_snapshot_status() -> None:
    scanner = CountingScanner()
    settings = Settings(database_url=TEST_DATABASE_URL, app_env="test")
    with TestClient(create_app(settings, market_data_provider=scanner)) as client:
        _configure_profile(client)
        created = client.post("/v1/proposal-sets", json={"contribution": "8000.00"})
        latest = client.get("/v1/market-research/latest")
        admission = client.get("/v1/asset-admission/latest")

    assert created.status_code == 201
    assert latest.status_code == 200
    payload = latest.json()
    assert payload["status"] == "succeeded"
    assert payload["provider"] == scanner.name
    assert payload["universe_size"] == 321
    assert datetime.fromisoformat(payload["observed_at"]).tzinfo is not None
    assert admission.status_code == 200
    admission_payload = admission.json()
    assert admission_payload["policy_version"] == "asset-admission-v3"
    assert len(admission_payload["issuer_evidence_set_hash"]) == 64
    assert admission_payload["assessment_count"] == 1
    assert admission_payload["status_counts"]["eligible"] == 1
    profile = admission_payload["assessments"][0]["profile"]
    assert admission_payload["assessments"][0]["issuer_evidence_snapshot_id"] is None
    assert profile["overall_status"] == "eligible"
    assert profile["liquidity"]["status"] == "eligible"
    assert profile["investment"]["status"] == "eligible"


def test_admission_assessments_are_append_only() -> None:
    scanner = CountingScanner()
    settings = Settings(database_url=TEST_DATABASE_URL, app_env="test")
    with TestClient(create_app(settings, market_data_provider=scanner)) as client:
        _configure_profile(client)
        created = client.post("/v1/proposal-sets", json={"contribution": "8000.00"})
    assert created.status_code == 201

    engine = create_engine(TEST_DATABASE_URL)
    with (
        pytest.raises(DBAPIError, match="immutable table asset_admission_assessments"),
        engine.begin() as connection,
    ):
        connection.execute(text("UPDATE asset_admission_assessments SET overall_status = 'reject'"))
    engine.dispose()


def test_new_issuer_facts_re_evaluate_the_same_market_snapshot() -> None:
    observed_at = datetime.fromisoformat("2026-08-16T15:30:00+00:00")
    rejected_bundle = replace(
        MOEX_ISSUER_EVIDENCE_V2,
        research=replace(
            MOEX_ISSUER_EVIDENCE_V2.research,
            payout_ratio_percent=Decimal("100.00000001"),
        ),
    )
    database = Database(TEST_DATABASE_URL)
    try:
        with database.sessions() as session:
            first = acquire_market_research(
                session,
                EquityScanner(),
                observed_at=observed_at,
                cache_seconds=14_400,
                issuer_evidence_provider=ReviewedIssuerCorpusProvider(),
            )
        with database.sessions() as session:
            second = acquire_market_research(
                session,
                EquityScanner(),
                observed_at=observed_at + timedelta(minutes=1),
                cache_seconds=14_400,
                issuer_evidence_provider=ReviewedIssuerCorpusProvider((rejected_bundle,)),
            )
    finally:
        database.close()

    assert first.record.id == second.record.id
    assert first.admission_run.id != second.admission_run.id
    assert first.admission_run.issuer_evidence_set_hash != (
        second.admission_run.issuer_evidence_set_hash
    )
    assert first.profiles["MOEX"].overall_status.value == "eligible"
    assert second.profiles["MOEX"].overall_status.value == "reject"

    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM market_research_snapshots")) == 1
        assert connection.scalar(text("SELECT count(*) FROM issuer_evidence_snapshots")) == 2
        assert connection.scalar(text("SELECT count(*) FROM asset_admission_runs")) == 2
    engine.dispose()


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
