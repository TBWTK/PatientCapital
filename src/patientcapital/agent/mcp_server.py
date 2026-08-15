"""Local stdio MCP server for Codex and other model clients."""

from collections.abc import Callable
from decimal import Decimal
from typing import Any
from uuid import UUID

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from patientcapital.agent.adapter import AgentTools
from patientcapital.config import Settings
from patientcapital.contracts import (
    AssetListResponse,
    DiscoveryRecommendationCreate,
    PortfolioResponse,
    ProfileResponse,
    RecommendationCreate,
    RecommendationResponse,
    TransactionCreate,
    TransactionResponse,
)
from patientcapital.marketdata.models import MarketDataProvider
from patientcapital.marketdata.moex import MoexIssProvider
from patientcapital.persistence.database import Database

READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)
PROPOSE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=False,
    open_world_hint=False,
)
DISCOVER_PROPOSE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=False,
    open_world_hint=True,
)
RECORD = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)


class StrictMCPServer(MCPServer):
    """MCPServer variant that rejects unknown top-level arguments.

    MCP SDK 2.0 generates argument models with Pydantic's default ``extra=ignore``.
    Financial tools fail closed instead: the advertised schema and runtime validator
    both use ``extra=forbid``.
    """

    def add_tool(
        self,
        fn: Callable[..., Any],
        name: str | None = None,
        title: str | None = None,
        description: str | None = None,
        annotations: ToolAnnotations | None = None,
        icons: list[Any] | None = None,
        meta: dict[str, Any] | None = None,
        structured_output: bool | None = None,
    ) -> None:
        super().add_tool(
            fn,
            name=name,
            title=title,
            description=description,
            annotations=annotations,
            icons=icons,
            meta=meta,
            structured_output=structured_output,
        )
        tool = self._tool_manager.get_tool(name or fn.__name__)
        if tool is None:  # pragma: no cover - guarded by MCPServer registration
            raise RuntimeError("registered MCP tool cannot be resolved")
        argument_model = tool.fn_metadata.arg_model
        argument_model.model_config["extra"] = "forbid"
        argument_model.model_rebuild(force=True)
        tool.parameters = argument_model.model_json_schema()


def build_mcp_server(
    database: Database, market_data_provider: MarketDataProvider | None = None
) -> MCPServer:
    """Build an MCP server around an injected database for runtime or contract tests."""

    tools = AgentTools(database, market_data_provider or MoexIssProvider())
    server = StrictMCPServer(
        name="patientcapital",
        title="PatientCapital",
        version="0.1.0",
        instructions=(
            "Use these tools only for the user's local PatientCapital data. Numbers are owned by "
            "the deterministic application core: never invent, modify, or recalculate them. A "
            "recommendation is a proposal, never proof of execution. Call record_transaction only "
            "for transaction facts the user explicitly confirms. Unknown or stale data must remain "
            "a visible error."
        ),
    )

    @server.tool(
        name="get_profile",
        title="Get investor profile",
        description="Read the latest versioned investor, broker fee, and cash-buffer profile.",
        annotations=READ_ONLY,
    )
    def get_profile_tool() -> ProfileResponse:
        return tools.get_profile()

    @server.tool(
        name="list_assets",
        title="List configured assets",
        description="Read the latest asset versions, lot sizes, currencies, and target weights.",
        annotations=READ_ONLY,
    )
    def list_assets_tool() -> AssetListResponse:
        return tools.list_assets()

    @server.tool(
        name="get_portfolio",
        title="Get portfolio analytics",
        description=(
            "Read ledger-derived positions, cost basis, market value, unrealized result, prices, "
            "target weights, and drift. Return values verbatim; do not recalculate them."
        ),
        annotations=READ_ONLY,
    )
    def get_portfolio_tool() -> PortfolioResponse:
        return tools.get_portfolio()

    @server.tool(
        name="propose_contribution",
        title="Propose contribution purchases",
        description=(
            "Create and persist an immutable, deterministic purchase proposal for a contribution. "
            "This never records a trade or changes positions."
        ),
        annotations=PROPOSE,
    )
    def propose_contribution_tool(contribution: Decimal) -> RecommendationResponse:
        return tools.propose_contribution(RecommendationCreate(contribution=contribution))

    @server.tool(
        name="discover_contribution",
        title="Discover instruments and propose contribution purchases",
        description=(
            "Fetch and validate delayed MOEX instrument facts, apply the versioned five-year "
            "selection policy, and persist a deterministic purchase proposal. The user supplies "
            "only the contribution; this never records or places a trade. Return run, policy, "
            "source, timestamp, and candidate fields verbatim."
        ),
        annotations=DISCOVER_PROPOSE,
    )
    def discover_contribution_tool(contribution: Decimal) -> RecommendationResponse:
        return tools.discover_contribution(DiscoveryRecommendationCreate(contribution=contribution))

    @server.tool(
        name="get_recommendation",
        title="Get saved recommendation",
        description="Retrieve one immutable recommendation run by UUID without recalculation.",
        annotations=READ_ONLY,
    )
    def get_recommendation_tool(run_id: UUID) -> RecommendationResponse:
        return tools.get_recommendation(run_id)

    @server.tool(
        name="record_transaction",
        title="Record confirmed transaction",
        description=(
            "Append one user-confirmed BUY or SELL fact. Never infer this call from a proposal. "
            "The caller must supply a unique idempotency key, actual quantity, price, fee, "
            "currency, and timezone-aware occurrence time. This does not place a broker order."
        ),
        annotations=RECORD,
    )
    def record_transaction_tool(transaction: TransactionCreate) -> TransactionResponse:
        return tools.record_transaction(transaction)

    return server


def main() -> None:
    """Run the local server over the stdio protocol channel."""

    database = Database(Settings().database_url)
    try:
        settings = Settings()
        provider = MoexIssProvider(
            base_url=settings.moex_iss_base_url,
            timeout_seconds=settings.moex_timeout_seconds,
            max_age_seconds=settings.moex_max_age_seconds,
        )
        build_mcp_server(database, provider).run(transport="stdio")
    finally:
        database.close()


if __name__ == "__main__":
    main()
