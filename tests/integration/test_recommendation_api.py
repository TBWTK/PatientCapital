from fastapi.testclient import TestClient

from tests.integration.helpers import seed_two_assets


def _record_buy(client: TestClient, asset_id: str, quantity: int, key: str) -> None:
    response = client.post(
        "/v1/transactions",
        json={
            "idempotency_key": key,
            "asset_id": asset_id,
            "side": "BUY",
            "quantity": quantity,
            "unit_price": "100.00",
            "fee": "0.00",
            "currency": "RUB",
            "occurred_at": "2026-08-15T08:00:00Z",
        },
    )
    assert response.status_code == 201, response.text


def test_api_persists_exact_domain_recommendation_snapshot(client: TestClient) -> None:
    seed_two_assets(client)
    _record_buy(client, "AAA", 10, "initial-aaa")
    _record_buy(client, "BBB", 20, "initial-bbb")

    response = client.post("/v1/recommendations", json={"contribution": "10000.00"})

    assert response.status_code == 201, response.text
    run = response.json()
    assert [(line["asset_id"], line["quantity"]) for line in run["lines"]] == [
        ("AAA", 49),
        ("BBB", 40),
    ]
    assert run["gross"] == "8900.00"
    assert run["fees"] == "8.90"
    assert run["leftover"] == "91.10"
    assert run["reason"] == "ALLOCATED"
    assert len(run["input_hash"]) == 64

    persisted = client.get(f"/v1/recommendations/{run['id']}")
    assert persisted.status_code == 200
    assert persisted.json() == run


def test_stale_manual_price_blocks_api_recommendation(client: TestClient) -> None:
    seed_two_assets(client)
    stale = client.post(
        "/v1/assets/AAA/prices",
        json={
            "price": "100.00",
            "currency": "RUB",
            "as_of": "2020-01-01T00:00:00Z",
            "max_age_seconds": 60,
            "source": "stale-test",
        },
    )
    assert stale.status_code == 201

    response = client.post("/v1/recommendations", json={"contribution": "10000.00"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "STALE_PRICE"
