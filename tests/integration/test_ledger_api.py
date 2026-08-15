from fastapi.testclient import TestClient

from tests.integration.helpers import seed_two_assets


def _buy_payload(*, key: str = "buy-aaa-1", quantity: int = 10) -> dict[str, object]:
    return {
        "idempotency_key": key,
        "asset_id": "AAA",
        "side": "BUY",
        "quantity": quantity,
        "unit_price": "100.00",
        "fee": "1.00",
        "currency": "RUB",
        "occurred_at": "2026-08-15T08:00:00Z",
        "note": "manual purchase",
    }


def test_transaction_is_idempotent_and_portfolio_is_derived(client: TestClient) -> None:
    seed_two_assets(client)

    created = client.post("/v1/transactions", json=_buy_payload())
    assert created.status_code == 201
    transaction_id = created.json()["id"]

    replay = client.post("/v1/transactions", json=_buy_payload())
    assert replay.status_code == 200
    assert replay.json()["id"] == transaction_id
    assert replay.json() == created.json()

    conflict = client.post("/v1/transactions", json=_buy_payload(quantity=11))
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

    portfolio = client.get("/v1/portfolio")
    assert portfolio.status_code == 200
    aaa = next(item for item in portfolio.json()["assets"] if item["asset_id"] == "AAA")
    assert aaa["quantity"] == 10
    assert aaa["market_value"] == "1000.00"
    assert aaa["cost_basis"] == "1001.00"
    assert aaa["unrealized_pnl"] == "-1.00"


def test_sell_cannot_create_a_hidden_negative_position(client: TestClient) -> None:
    seed_two_assets(client)
    payload = _buy_payload(key="sell-too-much", quantity=1)
    payload["side"] = "SELL"

    response = client.post("/v1/transactions", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INSUFFICIENT_POSITION"
