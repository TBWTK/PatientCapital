from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from patientcapital.application.errors import ApplicationError
from patientcapital.marketdata.errors import MarketDataError
from patientcapital.marketdata.models import InstrumentKind, MarketCandidate
from patientcapital.monitoring.service import acknowledge_alert, list_alerts, run_monitor
from patientcapital.persistence.database import Database
from tests.integration.conftest import TEST_DATABASE_URL


class MonitorProvider:
    name = "monitor-test-provider"

    def discover(self, *, calculated_at: datetime) -> tuple[MarketCandidate, ...]:
        return (
            MarketCandidate(
                asset_id="AAA",
                name="Asset A",
                kind=InstrumentKind.EQUITY_INDEX_FUND,
                currency="RUB",
                lot_size=1,
                unit_price=Decimal("120"),
                price_as_of=calculated_at - timedelta(minutes=5),
                max_age=timedelta(days=4),
                source_url="https://iss.moex.com/AAA",
                classification_url="https://www.moex.com/msn/etf",
                quote_kind="current",
                turnover=Decimal("100000000"),
            ),
        )


class FailingProvider:
    name = "monitor-failing-provider"

    def discover(self, *, calculated_at: datetime) -> tuple[MarketCandidate, ...]:
        del calculated_at
        raise MarketDataError("MOEX_UNAVAILABLE", "controlled outage")


class DuplicateProvider(MonitorProvider):
    def discover(self, *, calculated_at: datetime) -> tuple[MarketCandidate, ...]:
        candidate = super().discover(calculated_at=calculated_at)[0]
        return candidate, candidate


class EmptyProvider:
    name = "empty-provider"

    def discover(self, *, calculated_at: datetime) -> tuple[MarketCandidate, ...]:
        del calculated_at
        return ()


def _seed(client: TestClient) -> None:
    client.put(
        "/v1/profile",
        json={
            "expected_version": None,
            "base_currency": "RUB",
            "investment_horizon_years": 5,
            "risk_level": "growth",
            "cash_buffer": "0.00",
            "broker_name": "Test Broker",
            "fee_rate": "0.0005",
            "minimum_fee": "0.00",
        },
    )
    client.put(
        "/v1/assets/AAA",
        json={
            "expected_version": None,
            "name": "Asset A",
            "currency": "RUB",
            "lot_size": 1,
            "target_weight": "0.40000000",
            "is_active": True,
        },
    )
    client.post(
        "/v1/assets/AAA/prices",
        json={
            "price": "100",
            "currency": "RUB",
            "as_of": "2026-08-16T05:55:00Z",
            "max_age_seconds": 345600,
            "source": "fixture",
        },
    )
    client.post(
        "/v1/transactions",
        json={
            "idempotency_key": "monitor-seed-buy",
            "asset_id": "AAA",
            "side": "BUY",
            "quantity": 10,
            "unit_price": "100",
            "fee": "0",
            "currency": "RUB",
            "occurred_at": "2026-08-15T10:00:00Z",
        },
    )


def test_monitor_ticks_are_idempotent_dedupe_daily_alerts_and_never_trade(
    client: TestClient,
) -> None:
    _seed(client)
    database = Database(TEST_DATABASE_URL)
    observed = datetime(2026, 8, 16, 7, 1, tzinfo=UTC)
    with database.sessions() as session:
        first = run_monitor(
            session,
            MonitorProvider(),
            scheduled_for=datetime(2026, 8, 16, 7, 0, tzinfo=UTC),
            observed_at=observed,
        )
    with database.sessions() as session:
        replay = run_monitor(
            session,
            MonitorProvider(),
            scheduled_for=datetime(2026, 8, 16, 7, 0, tzinfo=UTC),
            observed_at=observed + timedelta(minutes=1),
        )
    with database.sessions() as session:
        second_slot = run_monitor(
            session,
            MonitorProvider(),
            scheduled_for=datetime(2026, 8, 16, 11, 0, tzinfo=UTC),
            observed_at=observed + timedelta(hours=4),
        )
    database.close()

    assert first.status == "alerts_created"
    assert first.alerts_created == 2
    assert replay.id == first.id
    assert second_slot.status == "no_change"
    assert second_slot.alerts_created == 0

    alerts = client.get("/v1/alerts").json()
    assert [item["kind"] for item in alerts["alerts"]] == ["price_move", "allocation_drift"]
    assert all(item["acknowledgement"] is None for item in alerts["alerts"])
    alert_id = alerts["alerts"][0]["id"]
    acknowledged = client.post(f"/v1/alerts/{alert_id}/acknowledgements", json={})
    assert acknowledged.status_code == 201
    replay_ack = client.post(f"/v1/alerts/{alert_id}/acknowledgements", json={})
    assert replay_ack.status_code == 200
    assert replay_ack.json() == acknowledged.json()

    runs = client.get("/v1/monitor-runs").json()
    assert len(runs["runs"]) == 2
    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM transactions")) == 1
        assert connection.scalar(text("SELECT count(*) FROM monitor_alerts")) == 2
    engine.dispose()


def test_provider_outage_is_persisted_without_alert_or_retry_guess(client: TestClient) -> None:
    _seed(client)
    database = Database(TEST_DATABASE_URL)
    with database.sessions() as session:
        run = run_monitor(
            session,
            FailingProvider(),
            scheduled_for=datetime(2026, 8, 16, 15, 0, tzinfo=UTC),
            observed_at=datetime(2026, 8, 16, 15, 1, tzinfo=UTC),
        )
    database.close()

    assert run.status == "provider_error"
    assert run.error_code == "MOEX_UNAVAILABLE"
    assert run.alerts_created == 0
    assert client.get("/v1/alerts").json()["alerts"] == []


def test_unconfigured_portfolio_persists_blocked_run_without_market_call(
    client: TestClient,
) -> None:
    class ProviderMustNotRun:
        name = "must-not-run"

        def discover(self, *, calculated_at: datetime) -> tuple[MarketCandidate, ...]:
            raise AssertionError(f"provider must not run at {calculated_at.isoformat()}")

    database = Database(TEST_DATABASE_URL)
    with database.sessions() as session:
        run = run_monitor(
            session,
            ProviderMustNotRun(),
            scheduled_for=datetime(2026, 8, 16, 7, 0, tzinfo=UTC),
            observed_at=datetime(2026, 8, 16, 7, 1, tzinfo=UTC),
        )
    database.close()

    assert run.status == "blocked"
    assert run.error_code == "PROFILE_NOT_CONFIGURED"
    assert client.get("/v1/alerts").json()["alerts"] == []


def test_monitor_boundaries_fail_closed_and_keep_unknown_state_visible(
    client: TestClient,
) -> None:
    _seed(client)
    database = Database(TEST_DATABASE_URL)
    with (
        database.sessions() as session,
        pytest.raises(ApplicationError, match="timezone-aware"),
    ):
        run_monitor(
            session,
            MonitorProvider(),
            scheduled_for=datetime(2026, 8, 16, 7),
            observed_at=datetime(2026, 8, 16, 7, 1, tzinfo=UTC),
        )
    with (
        database.sessions() as session,
        pytest.raises(ApplicationError, match="cannot precede"),
    ):
        run_monitor(
            session,
            MonitorProvider(),
            scheduled_for=datetime(2026, 8, 16, 7, 0, tzinfo=UTC),
            observed_at=datetime(2026, 8, 16, 6, 59, tzinfo=UTC),
        )
    with database.sessions() as session:
        duplicate = run_monitor(
            session,
            DuplicateProvider(),
            scheduled_for=datetime(2026, 8, 16, 7, 0, tzinfo=UTC),
            observed_at=datetime(2026, 8, 16, 7, 1, tzinfo=UTC),
        )
    with database.sessions() as session:
        missing = run_monitor(
            session,
            EmptyProvider(),
            scheduled_for=datetime(2026, 8, 16, 11, 0, tzinfo=UTC),
            observed_at=datetime(2026, 8, 16, 11, 1, tzinfo=UTC),
        )
    with database.sessions() as session:
        with pytest.raises(ApplicationError, match="between 1 and 100"):
            list_alerts(session, limit=0)
        with pytest.raises(ApplicationError, match="not found"):
            acknowledge_alert(session, UUID("00000000-0000-0000-0000-000000000099"))
    database.close()

    assert duplicate.status == "provider_error"
    assert duplicate.error_code == "MARKET_DATA_INVALID"
    assert missing.status == "provider_error"
    assert missing.error_code == "UNSUPPORTED_MARKET_HOLDING"
