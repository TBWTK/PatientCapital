"""Transport-neutral agent tools over the same application services as HTTP."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TypeVar
from uuid import UUID

from sqlalchemy.orm import Session

from patientcapital.application.errors import ApplicationError
from patientcapital.application.services import (
    create_recommendation,
    create_transaction,
    get_portfolio,
    get_profile,
    get_recommendation,
    list_assets,
)
from patientcapital.contracts import (
    AssetListResponse,
    ErrorDetail,
    ErrorResponse,
    PortfolioResponse,
    ProfileResponse,
    RecommendationCreate,
    RecommendationResponse,
    TransactionCreate,
    TransactionResponse,
)
from patientcapital.domain.errors import InvalidAllocationInput
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

    def __init__(self, database: Database) -> None:
        self._database = database

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

    def get_recommendation(self, run_id: UUID) -> RecommendationResponse:
        return self._call(lambda session: get_recommendation(session, run_id))

    def record_transaction(self, transaction: TransactionCreate) -> TransactionResponse:
        def record(session: Session) -> TransactionResponse:
            response, _created = create_transaction(session, transaction)
            return response

        return self._call(record)
