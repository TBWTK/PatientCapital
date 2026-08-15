import asyncio
import sys
from collections.abc import Awaitable, Callable
from typing import Any, cast

from fastapi.testclient import TestClient
from mcp import Client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult, ListToolsResult, TextContent

from patientcapital.agent.mcp_server import build_mcp_server
from patientcapital.persistence.database import Database
from tests.integration.conftest import TEST_DATABASE_URL
from tests.integration.helpers import seed_two_assets


async def _with_mcp[ResultT](operation: Callable[[Client], Awaitable[ResultT]]) -> ResultT:
    database = Database(TEST_DATABASE_URL)
    try:
        async with Client(build_mcp_server(database)) as mcp_client:
            return await operation(mcp_client)
    finally:
        database.close()


def _run[ResultT](operation: Callable[[Client], Awaitable[ResultT]]) -> ResultT:
    return asyncio.run(_with_mcp(operation))


def _error_text(result: CallToolResult) -> str:
    return " ".join(block.text for block in result.content if isinstance(block, TextContent))


def test_mcp_discovery_is_allowlisted_typed_and_permission_annotated() -> None:
    async def discover(client: Client) -> ListToolsResult:
        return await client.list_tools()

    discovered = _run(discover)
    by_name = {tool.name: tool for tool in discovered.tools}

    assert set(by_name) == {
        "get_profile",
        "list_assets",
        "get_portfolio",
        "propose_contribution",
        "get_recommendation",
        "record_transaction",
    }
    assert by_name["get_portfolio"].annotations is not None
    assert by_name["get_portfolio"].annotations.read_only_hint is True
    assert by_name["get_portfolio"].annotations.open_world_hint is False
    assert by_name["propose_contribution"].annotations is not None
    assert by_name["propose_contribution"].annotations.read_only_hint is False
    assert by_name["propose_contribution"].annotations.idempotent_hint is False
    assert by_name["record_transaction"].annotations is not None
    assert by_name["record_transaction"].annotations.idempotent_hint is True
    assert by_name["record_transaction"].input_schema["additionalProperties"] is False
    assert by_name["propose_contribution"].output_schema is not None


def test_real_stdio_entrypoint_negotiates_and_lists_tools() -> None:
    async def discover_from_process() -> ListToolsResult:
        transport = stdio_client(
            StdioServerParameters(
                command=sys.executable,
                args=["-m", "patientcapital.agent.mcp_server"],
            )
        )
        async with Client(transport) as mcp_client:
            return await mcp_client.list_tools()

    discovered = asyncio.run(discover_from_process())
    assert {tool.name for tool in discovered.tools} >= {
        "get_portfolio",
        "propose_contribution",
        "record_transaction",
    }


def test_mcp_missing_profile_is_a_machine_coded_tool_error() -> None:
    async def get_missing_profile(mcp_client: Client) -> CallToolResult:
        return await mcp_client.call_tool("get_profile", {})

    result = _run(get_missing_profile)
    assert result.is_error is True
    assert '"code":"PROFILE_NOT_CONFIGURED"' in _error_text(result)


def test_mcp_proposal_is_the_same_immutable_run_retrieved_by_http(
    client: TestClient,
) -> None:
    seed_two_assets(client)
    for asset_id, quantity in (("AAA", 10), ("BBB", 20)):
        response = client.post(
            "/v1/transactions",
            json={
                "idempotency_key": f"agent-seed-{asset_id}",
                "asset_id": asset_id,
                "side": "BUY",
                "quantity": quantity,
                "unit_price": "100.00",
                "fee": "0.00",
                "currency": "RUB",
                "occurred_at": "2026-08-15T08:00:00Z",
            },
        )
        assert response.status_code == 201

    async def propose(
        mcp_client: Client,
    ) -> tuple[CallToolResult, CallToolResult, CallToolResult, CallToolResult]:
        profile = await mcp_client.call_tool("get_profile", {})
        assets = await mcp_client.call_tool("list_assets", {})
        portfolio = await mcp_client.call_tool("get_portfolio", {})
        proposal = await mcp_client.call_tool("propose_contribution", {"contribution": "10000.00"})
        return profile, assets, portfolio, proposal

    profile_result, assets_result, portfolio_result, result = _run(propose)
    assert profile_result.is_error is False
    assert cast(dict[str, Any], profile_result.structured_content)["version"] == 1
    assert assets_result.is_error is False
    assert len(cast(dict[str, Any], assets_result.structured_content)["assets"]) == 2
    assert portfolio_result.is_error is False
    portfolio_output = cast(dict[str, Any], portfolio_result.structured_content)
    assert portfolio_output["total_market_value"] == "3000.00"
    assert result.is_error is False
    run = cast(dict[str, Any], result.structured_content)
    assert run["gross"] == "8900.00"
    assert run["fees"] == "8.90"
    assert run["leftover"] == "91.10"
    assert run["algorithm_version"] == "contribution-greedy-v1"
    assert len(cast(str, run["input_hash"])) == 64

    persisted = client.get(f"/v1/recommendations/{run['id']}")
    assert persisted.status_code == 200
    assert persisted.json() == run

    async def retrieve(mcp_client: Client) -> CallToolResult:
        return await mcp_client.call_tool("get_recommendation", {"run_id": run["id"]})

    retrieved = _run(retrieve)
    assert retrieved.is_error is False
    assert retrieved.structured_content == run


def test_mcp_record_transaction_preserves_exact_replay(client: TestClient) -> None:
    seed_two_assets(client)
    transaction = {
        "idempotency_key": "agent-confirmed-buy-1",
        "asset_id": "AAA",
        "side": "BUY",
        "quantity": 3,
        "unit_price": "101.25",
        "fee": "1.00",
        "currency": "RUB",
        "occurred_at": "2026-08-15T09:00:00Z",
        "note": "explicit user-confirmed purchase",
    }

    async def record_twice(mcp_client: Client) -> tuple[CallToolResult, CallToolResult]:
        first = await mcp_client.call_tool("record_transaction", {"transaction": transaction})
        replay = await mcp_client.call_tool("record_transaction", {"transaction": transaction})
        return first, replay

    first, replay = _run(record_twice)
    assert first.is_error is False
    assert replay.is_error is False
    assert first.structured_content == replay.structured_content
    portfolio = client.get("/v1/portfolio").json()
    aaa = next(item for item in portfolio["assets"] if item["asset_id"] == "AAA")
    assert aaa["quantity"] == 3


def test_mcp_expected_failures_are_visible_and_machine_coded(client: TestClient) -> None:
    seed_two_assets(client)
    stale = client.post(
        "/v1/assets/AAA/prices",
        json={
            "price": "100.00",
            "currency": "RUB",
            "as_of": "2020-01-01T00:00:00Z",
            "max_age_seconds": 60,
            "source": "stale-agent-test",
        },
    )
    assert stale.status_code == 201

    async def fail_safely(
        mcp_client: Client,
    ) -> tuple[CallToolResult, CallToolResult, CallToolResult]:
        stale_result = await mcp_client.call_tool(
            "propose_contribution", {"contribution": "10000.00"}
        )
        extra_result = await mcp_client.call_tool("get_profile", {"unexpected": True})
        unknown_result = await mcp_client.call_tool("arbitrary_sql", {"query": "SELECT 1"})
        return stale_result, extra_result, unknown_result

    stale_result, extra_result, unknown_result = _run(fail_safely)
    assert stale_result.is_error is True
    assert '"code":"STALE_PRICE"' in _error_text(stale_result)
    assert extra_result.is_error is True
    assert "unexpected" in _error_text(extra_result)
    assert unknown_result.is_error is True
    assert "Unknown tool" in _error_text(unknown_result)
