from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from patientcapital.api.app import create_app
from patientcapital.config import Settings
from patientcapital.marketdata.models import InstrumentKind, MarketCandidate
from tests.integration.conftest import TEST_DATABASE_URL


class StaticMarketDataProvider:
    name = "moex-iss-test-fixture"

    def discover(self, *, calculated_at: datetime) -> tuple[MarketCandidate, ...]:
        return (
            MarketCandidate(
                asset_id="SU26218RMFS6",
                name="ОФЗ 26218",
                kind=InstrumentKind.OFZ,
                currency="RUB",
                lot_size=1,
                unit_price=Decimal("818.21000000"),
                price_as_of=calculated_at - timedelta(hours=1),
                max_age=timedelta(days=4),
                source_url="https://iss.moex.com/ofz",
                classification_url="https://www.moex.com/ru/marketdata/",
                quote_kind="last_dirty",
                turnover=Decimal("742285912"),
                maturity_date=date(2031, 9, 17),
                yield_percent=Decimal("15.19"),
                clean_price_percent=Decimal("78.445"),
                face_value=Decimal("1000"),
                accrued_interest=Decimal("33.76"),
            ),
            MarketCandidate(
                asset_id="EQMX",
                name="ВИМ — Индекс МосБиржи",
                kind=InstrumentKind.EQUITY_INDEX_FUND,
                currency="RUB",
                lot_size=1,
                unit_price=Decimal("117.35000000"),
                price_as_of=calculated_at - timedelta(hours=1),
                max_age=timedelta(days=4),
                source_url="https://iss.moex.com/eqmx",
                classification_url="https://www.moex.com/msn/etf",
                quote_kind="current",
                turnover=Decimal("601551768"),
            ),
            MarketCandidate(
                asset_id="FUNDALT",
                name="Альтернативный индексный фонд",
                kind=InstrumentKind.EQUITY_INDEX_FUND,
                currency="RUB",
                lot_size=1,
                unit_price=Decimal("120.00000000"),
                price_as_of=calculated_at - timedelta(hours=1),
                max_age=timedelta(days=4),
                source_url="https://iss.moex.com/fundalt",
                classification_url="https://www.moex.com/msn/etf",
                quote_kind="current",
                turnover=Decimal("1000"),
            ),
        )


def _client() -> TestClient:
    app = create_app(
        Settings(database_url=TEST_DATABASE_URL, app_env="test"),
        market_data_provider=StaticMarketDataProvider(),
    )
    return TestClient(app)


def test_amount_only_flow_materializes_market_evidence_and_does_not_trade() -> None:
    with _client() as client:
        profile = client.put(
            "/v1/profile",
            json={
                "expected_version": None,
                "base_currency": "RUB",
                "investment_horizon_years": 5,
                "risk_level": "balanced",
                "cash_buffer": "0.00",
                "broker_name": "Test Broker",
                "fee_rate": "0.001",
                "minimum_fee": "1.00",
            },
        )
        assert profile.status_code == 200

        response = client.post("/v1/discovery/recommendations", json={"contribution": "8000.00"})

        assert response.status_code == 201, response.text
        run = response.json()
        assert run["mode"] == "automatic"
        assert run["horizon_years"] == 5
        assert run["risk_level"] == "balanced"
        assert run["policy_version"] == "five-year-moex-v1"
        assert [(item["asset_id"], item["target_weight"]) for item in run["candidates"]] == [
            ("SU26218RMFS6", "0.60000000"),
            ("EQMX", "0.40000000"),
        ]
        assert Decimal(run["spent"]) <= Decimal("8000.00")
        assert run["lines"]
        assert all(item["source_url"].startswith("https://") for item in run["candidates"])
        assert [item["asset_id"] for item in run["rejected_candidates"]] == ["FUNDALT"]
        assert "ranking" in run["rejected_candidates"][0]["reason"]

        assets = client.get("/v1/assets").json()["assets"]
        assert {item["asset_id"] for item in assets if item["is_active"]} == {
            "SU26218RMFS6",
            "EQMX",
        }
        saved = client.get(f"/v1/recommendations/{run['id']}")
        assert saved.status_code == 200
        assert saved.json() == run

    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM transactions")) == 0
        assert connection.scalar(text("SELECT count(*) FROM price_snapshots")) == 2
    engine.dispose()


def test_discovery_blocks_non_five_year_profile() -> None:
    with _client() as client:
        client.put(
            "/v1/profile",
            json={
                "expected_version": None,
                "base_currency": "RUB",
                "investment_horizon_years": 15,
                "risk_level": "balanced",
                "cash_buffer": "0.00",
                "broker_name": "Test Broker",
                "fee_rate": "0.001",
                "minimum_fee": "1.00",
            },
        )

        response = client.post("/v1/discovery/recommendations", json={"contribution": "8000.00"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_DISCOVERY_HORIZON"
