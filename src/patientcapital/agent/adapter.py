"""Transport-neutral agent tools over the same application services as HTTP."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TypeVar
from uuid import UUID

from sqlalchemy.orm import Session

from patientcapital.application.errors import ApplicationError
from patientcapital.application.services import (
    create_discovery_recommendation,
    create_proposal_set,
    create_recommendation,
    create_transaction,
    create_transaction_draft_from_text,
    decide_transaction_draft,
    get_portfolio,
    get_profile,
    get_proposal_set,
    get_recommendation,
    get_transaction_draft,
    list_assets,
)
from patientcapital.contracts import (
    AssetListResponse,
    DiscoveryRecommendationCreate,
    ErrorDetail,
    ErrorResponse,
    PortfolioResponse,
    ProfileResponse,
    ProposalSetCreate,
    ProposalSetResponse,
    RecommendationCreate,
    RecommendationResponse,
    TransactionCreate,
    TransactionDraftDecisionCreate,
    TransactionDraftResponse,
    TransactionDraftTextCreate,
    TransactionResponse,
)
from patientcapital.domain.errors import InvalidAllocationInput
from patientcapital.marketdata.models import MarketDataProvider
from patientcapital.persistence.database import Database

ResultT = TypeVar("ResultT")


class AgentToolError(RuntimeError):
    """Expected failure encoded with the same envelope as the HTTP adapter."""

    def __init__(self, code: str, message: str) -> None:
        self.envelope = ErrorResponse(error=ErrorDetail(code=code, message=message))
        serialized = json.dumps(
            self.envelope.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        super().__init__(serialized)


class AgentTools:
    """Narrow read/propose/record use cases; no SQL, secrets, or broker execution."""

    def __init__(
        self, database: Database, market_data_provider: MarketDataProvider | None = None
    ) -> None:
        self._database = database
        self._market_data_provider = market_data_provider

    def _call(self, operation: Callable[[Session], ResultT]) -> ResultT:
        try:
            with self._database.sessions() as session:
                return operation(session)
        except ApplicationError as error:
            raise AgentToolError(error.code, error.message) from error
        except InvalidAllocationInput as error:
            raise AgentToolError(error.code, error.detail) from error

    def get_profile(self) -> ProfileResponse:
        return self._call(get_profile)

    def list_assets(self) -> AssetListResponse:
        return self._call(list_assets)

    def get_portfolio(self) -> PortfolioResponse:
        return self._call(get_portfolio)

    def propose_contribution(self, contribution: RecommendationCreate) -> RecommendationResponse:
        return self._call(lambda session: create_recommendation(session, contribution))

    def discover_contribution(
        self, contribution: DiscoveryRecommendationCreate
    ) -> RecommendationResponse:
        provider = self._market_data_provider
        if provider is None:
            raise AgentToolError(
                "MARKET_DATA_NOT_CONFIGURED", "market data provider is unavailable"
            )
        return self._call(
            lambda session: create_discovery_recommendation(session, contribution, provider)
        )

    def propose_strategy_set(self, contribution: ProposalSetCreate) -> ProposalSetResponse:
        provider = self._market_data_provider
        if provider is None:
            raise AgentToolError(
                "MARKET_DATA_NOT_CONFIGURED", "market data provider is unavailable"
            )
        return self._call(lambda session: create_proposal_set(session, contribution, provider))

    def get_proposal_set(self, proposal_set_id: UUID) -> ProposalSetResponse:
        return self._call(lambda session: get_proposal_set(session, proposal_set_id))

    def get_recommendation(self, run_id: UUID) -> RecommendationResponse:
        return self._call(lambda session: get_recommendation(session, run_id))

    def create_transaction_draft(
        self, payload: TransactionDraftTextCreate
    ) -> TransactionDraftResponse:
        return self._call(lambda session: create_transaction_draft_from_text(session, payload))

    def get_transaction_draft(self, draft_id: UUID) -> TransactionDraftResponse:
        return self._call(lambda session: get_transaction_draft(session, draft_id))

    def decide_transaction_draft(
        self,
        draft_id: UUID,
        payload: TransactionDraftDecisionCreate,
    ) -> TransactionDraftResponse:
        def decide(session: Session) -> TransactionDraftResponse:
            response, _created = decide_transaction_draft(session, draft_id, payload)
            return response

        return self._call(decide)

    def record_transaction(self, transaction: TransactionCreate) -> TransactionResponse:
        def record(session: Session) -> TransactionResponse:
            response, _created = create_transaction(session, transaction)
            return response

        return self._call(record)
