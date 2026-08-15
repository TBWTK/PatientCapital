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


def test_bond_purchase_preserves_clean_price_accrued_interest_and_cash_cost(
    client: TestClient,
) -> None:
    seed_two_assets(client)
    payload = {
        "idempotency_key": "t-invest-20260813-su26226-buy-7-1634",
        "asset_id": "AAA",
        "side": "BUY",
        "quantity": 7,
        "unit_price": "992.04",
        "accrued_interest_total": "195.16",
        "fee": "3.47",
        "currency": "RUB",
        "occurred_at": "2026-08-13T13:34:00Z",
        "note": "screenshot-backed OFZ purchase",
    }

    created = client.post("/v1/transactions", json=payload)

    assert created.status_code == 201, created.text
    assert created.json()["unit_price"] == "992.04000000"
    assert created.json()["accrued_interest_total"] == "195.16"
    portfolio = client.get("/v1/portfolio").json()
    asset = next(item for item in portfolio["assets"] if item["asset_id"] == "AAA")
    assert asset["quantity"] == 7
    assert asset["cost_basis"] == "7142.91"

    changed_nkd = {**payload, "accrued_interest_total": "195.17"}
    conflict = client.post("/v1/transactions", json=changed_nkd)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_legacy_transaction_payload_defaults_accrued_interest_to_zero(
    client: TestClient,
) -> None:
    seed_two_assets(client)

    created = client.post("/v1/transactions", json=_buy_payload())

    assert created.status_code == 201
    assert created.json()["accrued_interest_total"] == "0.00"


def test_sell_cannot_create_a_hidden_negative_position(client: TestClient) -> None:
    seed_two_assets(client)
    payload = _buy_payload(key="sell-too-much", quantity=1)
    payload["side"] = "SELL"

    response = client.post("/v1/transactions", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INSUFFICIENT_POSITION"
