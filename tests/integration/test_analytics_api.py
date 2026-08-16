from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tests.integration.helpers import post_price, put_asset, put_profile


def _transaction(
    client: TestClient,
    *,
    key: str,
    side: str,
    quantity: int,
    price: str,
    accrued_interest: str,
    fee: str,
    occurred_at: str,
) -> None:
    response = client.post(
        "/v1/transactions",
        json={
            "idempotency_key": key,
            "asset_id": "AAA",
            "side": side,
            "quantity": quantity,
            "unit_price": price,
            "accrued_interest_total": accrued_interest,
            "fee": fee,
            "currency": "RUB",
            "occurred_at": occurred_at,
        },
    )
    assert response.status_code == 201, response.text


def test_analytics_distinguishes_derived_results_from_unsupported_cashflows(
    client: TestClient,
) -> None:
    put_profile(client)
    put_asset(client, "AAA", name="Asset A", target_weight="1")
    post_price(client, "AAA", "110.00")
    _transaction(
        client,
        key="analytics-buy",
        side="BUY",
        quantity=10,
        price="100.00",
        accrued_interest="0.00",
        fee="10.00",
        occurred_at="2026-08-14T09:00:00Z",
    )
    _transaction(
        client,
        key="analytics-sell",
        side="SELL",
        quantity=4,
        price="120.00",
        accrued_interest="2.00",
        fee="2.00",
        occurred_at="2026-08-15T09:00:00Z",
    )

    response = client.get("/v1/analytics/overview")

    assert response.status_code == 200, response.text
    overview = response.json()
    assert overview["algorithm_version"] == "analytics-ledger-v1"
    assert overview["market_value"] == {
        "status": "available",
        "value": "660.00",
        "reason": None,
    }
    assert overview["cost_basis"]["value"] == "606.00"
    assert overview["unrealized_result"]["value"] == "54.00"
    assert overview["realized_result"]["value"] == "76.00"
    assert overview["net_contributions"] == {
        "status": "not_configured",
        "value": None,
        "reason": "DEPOSIT/WITHDRAWAL events are not configured in the ledger",
    }
    assert overview["income"] == {
        "status": "not_configured",
        "value": None,
        "reason": "COUPON/DIVIDEND events are not configured in the ledger",
    }
    assert overview["price_freshness"]["status"] == "fresh"
    assert overview["price_freshness"]["assets"][0]["asset_id"] == "AAA"
    assert [event["idempotency_key"] for event in overview["recent_activity"]] == [
        "analytics-sell",
        "analytics-buy",
    ]
    assert overview["allocation"][0]["quantity"] == 6


def test_analytics_marks_stale_prices_instead_of_hiding_freshness(
    client: TestClient,
) -> None:
    put_profile(client)
    put_asset(client, "AAA", name="Asset A", target_weight="1")
    response = client.post(
        "/v1/assets/AAA/prices",
        json={
            "price": "100.00",
            "currency": "RUB",
            "as_of": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
            "max_age_seconds": 60,
            "source": "stale-analytics-test",
        },
    )
    assert response.status_code == 201

    overview = client.get("/v1/analytics/overview")

    assert overview.status_code == 200
    freshness = overview.json()["price_freshness"]
    assert freshness["status"] == "stale"
    assert freshness["reason"] == "one or more portfolio prices are stale"
    assert freshness["assets"][0]["status"] == "stale"
