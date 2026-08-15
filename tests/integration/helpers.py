from datetime import UTC, datetime
from typing import cast

from fastapi.testclient import TestClient


def put_profile(client: TestClient, *, expected_version: int | None = None) -> dict[str, object]:
    response = client.put(
        "/v1/profile",
        json={
            "expected_version": expected_version,
            "base_currency": "RUB",
            "investment_horizon_years": 15,
            "risk_level": "balanced",
            "cash_buffer": "1000.00",
            "broker_name": "Test Broker",
            "fee_rate": "0.001",
            "minimum_fee": "1.00",
        },
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, object], response.json())


def put_asset(
    client: TestClient,
    asset_id: str,
    *,
    name: str,
    target_weight: str,
    expected_version: int | None = None,
) -> dict[str, object]:
    response = client.put(
        f"/v1/assets/{asset_id}",
        json={
            "expected_version": expected_version,
            "name": name,
            "currency": "RUB",
            "lot_size": 1,
            "target_weight": target_weight,
            "is_active": True,
        },
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, object], response.json())


def post_price(client: TestClient, asset_id: str, price: str) -> dict[str, object]:
    response = client.post(
        f"/v1/assets/{asset_id}/prices",
        json={
            "price": price,
            "currency": "RUB",
            "as_of": datetime.now(UTC).isoformat(),
            "max_age_seconds": 86400,
            "source": "manual-test",
        },
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, object], response.json())


def seed_two_assets(client: TestClient) -> None:
    put_profile(client)
    put_asset(client, "AAA", name="Asset A", target_weight="0.5")
    put_asset(client, "BBB", name="Asset B", target_weight="0.5")
    post_price(client, "AAA", "100.00")
    post_price(client, "BBB", "100.00")
