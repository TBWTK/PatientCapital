from fastapi.testclient import TestClient

from tests.integration.helpers import put_asset, put_profile


def test_health_distinguishes_process_and_database_readiness(client: TestClient) -> None:
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ready"}


def test_local_web_origin_receives_narrow_cors_headers(client: TestClient) -> None:
    response = client.options(
        "/v1/profile",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "GET" in response.headers["access-control-allow-methods"]
    assert "*" not in response.headers["access-control-allow-origin"]


def test_profile_uses_optimistic_append_only_versions(client: TestClient) -> None:
    missing = client.get("/v1/profile")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "PROFILE_NOT_CONFIGURED"

    first = put_profile(client)
    assert first["version"] == 1
    assert "api_key" not in first
    assert "client_id" not in first

    second = put_profile(client, expected_version=1)
    assert second["version"] == 2
    assert client.get("/v1/profile").json()["version"] == 2

    stale = client.put(
        "/v1/profile",
        json={
            "expected_version": 1,
            "base_currency": "RUB",
            "investment_horizon_years": 10,
            "risk_level": "conservative",
            "cash_buffer": "0.00",
            "broker_name": "Other",
            "fee_rate": "0.001",
            "minimum_fee": "1.00",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"


def test_asset_configuration_uses_the_same_version_contract(client: TestClient) -> None:
    first = put_asset(client, "AAA", name="Asset A", target_weight="1")
    assert first["version"] == 1

    second = put_asset(
        client,
        "AAA",
        name="Renamed Asset A",
        target_weight="1",
        expected_version=1,
    )
    assert second["version"] == 2

    stale = client.put(
        "/v1/assets/AAA",
        json={
            "expected_version": 1,
            "name": "Stale",
            "currency": "RUB",
            "lot_size": 1,
            "target_weight": "1",
            "is_active": True,
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"
