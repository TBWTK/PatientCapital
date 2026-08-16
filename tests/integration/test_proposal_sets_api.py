from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from patientcapital.api.app import create_app
from patientcapital.config import Settings
from tests.integration.conftest import TEST_DATABASE_URL
from tests.integration.test_discovery_recommendation_api import StaticMarketDataProvider


def _client() -> TestClient:
    return TestClient(
        create_app(
            Settings(database_url=TEST_DATABASE_URL, app_env="test"),
            market_data_provider=StaticMarketDataProvider(),
        )
    )


def test_amount_creates_one_admitted_recommended_strategy_without_trading() -> None:
    with _client() as client:
        profile = client.put(
            "/v1/profile",
            json={
                "expected_version": None,
                "base_currency": "RUB",
                "investment_horizon_years": 5,
                "risk_level": "growth",
                "cash_buffer": "0.00",
                "broker_name": "Т-Инвестиции",  # noqa: RUF001
                "fee_rate": "0.0005",
                "minimum_fee": "0.00",
            },
        )
        assert profile.status_code == 200

        response = client.post("/v1/proposal-sets", json={"contribution": "8000.00"})

        assert response.status_code == 201, response.text
        proposal_set = response.json()
        assert proposal_set["contribution"] == "8000.00"
        assert proposal_set["currency"] == "RUB"
        assert proposal_set["profile_version"] == 1
        assert proposal_set["recommended_strategy_id"] == "five_year_core"
        assert len(proposal_set["strategies"]) == 1
        strategy = proposal_set["strategies"][0]
        assert strategy["strategy_id"] == "five_year_core"
        assert strategy["name"] == "Основной план"
        assert strategy["recommended"] is True
        assert strategy["recommendation"]["policy_version"] == "five-year-moex-v2"
        assert strategy["recommendation"]["risk_level"] == "growth"
        assert Decimal(strategy["recommendation"]["spent"]) <= Decimal("8000.00")
        assert strategy["recommendation"]["lines"]

        saved = client.get(f"/v1/proposal-sets/{proposal_set['id']}")
        assert saved.status_code == 200
        assert saved.json() == proposal_set

    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM proposal_sets")) == 1
        assert connection.scalar(text("SELECT count(*) FROM recommendation_runs")) == 1
        assert connection.scalar(text("SELECT count(*) FROM transactions")) == 0
    engine.dispose()


def test_proposal_set_requires_configured_profile() -> None:
    with _client() as client:
        response = client.post("/v1/proposal-sets", json={"contribution": "8000.00"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROFILE_NOT_CONFIGURED"
