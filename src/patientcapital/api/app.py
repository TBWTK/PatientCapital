"""FastAPI application factory."""

from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, File, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from patientcapital.application.errors import ApplicationError
from patientcapital.application.services import (
    create_discovery_recommendation,
    create_price,
    create_proposal_set,
    create_recommendation,
    create_transaction,
    create_transaction_draft_from_image,
    create_transaction_draft_from_text,
    create_transaction_draft_manual,
    decide_transaction_draft,
    get_analytics_overview,
    get_latest_market_research,
    get_portfolio,
    get_profile,
    get_proposal_set,
    get_recommendation,
    get_transaction_draft,
    list_assets,
    put_asset,
    put_profile,
)
from patientcapital.config import Settings
from patientcapital.contracts import (
    AlertAcknowledgeCreate,
    AlertAcknowledgementResponse,
    AnalyticsOverviewResponse,
    AssetListResponse,
    AssetPut,
    AssetResponse,
    DiscoveryRecommendationCreate,
    ErrorResponse,
    MarketResearchStatusResponse,
    MonitorAlertListResponse,
    MonitorRunListResponse,
    PortfolioResponse,
    PriceCreate,
    PriceResponse,
    ProfilePut,
    ProfileResponse,
    ProposalSetCreate,
    ProposalSetResponse,
    RecommendationCreate,
    RecommendationResponse,
    TransactionCreate,
    TransactionDraftDecisionCreate,
    TransactionDraftManualCreate,
    TransactionDraftResponse,
    TransactionDraftTextCreate,
    TransactionResponse,
)
from patientcapital.domain.errors import InvalidAllocationInput
from patientcapital.marketdata.models import MarketDataProvider
from patientcapital.marketdata.moex import MoexIssProvider
from patientcapital.monitoring.service import acknowledge_alert, list_alerts, list_monitor_runs
from patientcapital.persistence.database import Database
from patientcapital.transaction_intake.image import ImageTextExtractor, TesseractImageExtractor


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def create_app(
    settings: Settings | None = None,
    market_data_provider: MarketDataProvider | None = None,
    image_text_extractor: ImageTextExtractor | None = None,
) -> FastAPI:
    resolved = settings or Settings()
    database = Database(resolved.database_url)
    provider = market_data_provider or MoexIssProvider(
        base_url=resolved.moex_iss_base_url,
        timeout_seconds=resolved.moex_timeout_seconds,
        max_age_seconds=resolved.moex_max_age_seconds,
        stock_prefilter_limit=resolved.market_research_stock_prefilter_limit,
    )
    extractor = image_text_extractor or TesseractImageExtractor(
        max_bytes=resolved.upload_max_bytes,
        max_pixels=resolved.upload_max_pixels,
        timeout_seconds=resolved.ocr_timeout_seconds,
        temp_directory=resolved.upload_temp_directory,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        database.close()

    app = FastAPI(
        title="PatientCapital API",
        version="0.1.0",
        lifespan=lifespan,
        responses={
            409: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
        },
    )
    app.state.database = database
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    def session_dependency() -> Generator[Session]:
        with database.sessions() as session:
            yield session

    SessionDependency = Annotated[Session, Depends(session_dependency)]

    @app.exception_handler(ApplicationError)
    async def application_error_handler(_: Request, exc: ApplicationError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.message)

    @app.exception_handler(InvalidAllocationInput)
    async def domain_error_handler(_: Request, exc: InvalidAllocationInput) -> JSONResponse:
        return _error(422, exc.code, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {"msg": "invalid request"}
        return _error(422, "REQUEST_VALIDATION_ERROR", str(first.get("msg", "invalid request")))

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", response_model=None)
    def ready(session: SessionDependency) -> Response | dict[str, str]:
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return _error(503, "DATABASE_UNAVAILABLE", "database readiness check failed")
        return {"status": "ready"}

    @app.get("/v1/profile", response_model=ProfileResponse)
    def profile_get(session: SessionDependency) -> ProfileResponse:
        return get_profile(session)

    @app.put("/v1/profile", response_model=ProfileResponse)
    def profile_put(payload: ProfilePut, session: SessionDependency) -> ProfileResponse:
        return put_profile(session, payload)

    @app.get("/v1/assets", response_model=AssetListResponse)
    def assets_get(session: SessionDependency) -> AssetListResponse:
        return list_assets(session)

    @app.put("/v1/assets/{asset_id}", response_model=AssetResponse)
    def asset_put(asset_id: str, payload: AssetPut, session: SessionDependency) -> AssetResponse:
        return put_asset(session, asset_id, payload)

    @app.post("/v1/assets/{asset_id}/prices", response_model=PriceResponse, status_code=201)
    def price_post(
        asset_id: str, payload: PriceCreate, session: SessionDependency
    ) -> PriceResponse:
        return create_price(session, asset_id, payload)

    @app.post("/v1/transactions", response_model=TransactionResponse, status_code=201)
    def transaction_post(
        payload: TransactionCreate,
        response: Response,
        session: SessionDependency,
    ) -> TransactionResponse:
        result, created = create_transaction(session, payload)
        response.status_code = 201 if created else 200
        return result

    @app.post(
        "/v1/transaction-drafts/text",
        response_model=TransactionDraftResponse,
        status_code=201,
    )
    def transaction_draft_text_post(
        payload: TransactionDraftTextCreate,
        session: SessionDependency,
    ) -> TransactionDraftResponse:
        return create_transaction_draft_from_text(session, payload)

    @app.post(
        "/v1/transaction-drafts/manual",
        response_model=TransactionDraftResponse,
        status_code=201,
    )
    def transaction_draft_manual_post(
        payload: TransactionDraftManualCreate,
        session: SessionDependency,
    ) -> TransactionDraftResponse:
        return create_transaction_draft_manual(session, payload)

    @app.post(
        "/v1/transaction-drafts/image",
        response_model=TransactionDraftResponse,
        status_code=201,
    )
    async def transaction_draft_image_post(
        session: SessionDependency,
        file: Annotated[UploadFile, File()],
    ) -> TransactionDraftResponse:
        content = await file.read(resolved.upload_max_bytes + 1)
        return create_transaction_draft_from_image(
            session,
            content=content,
            declared_content_type=file.content_type or "application/octet-stream",
            extractor=extractor,
        )

    @app.get(
        "/v1/transaction-drafts/{draft_id}", response_model=TransactionDraftResponse
    )
    def transaction_draft_get(
        draft_id: UUID,
        session: SessionDependency,
    ) -> TransactionDraftResponse:
        return get_transaction_draft(session, draft_id)

    @app.post(
        "/v1/transaction-drafts/{draft_id}/decisions",
        response_model=TransactionDraftResponse,
        status_code=201,
    )
    def transaction_draft_decision_post(
        draft_id: UUID,
        payload: TransactionDraftDecisionCreate,
        response: Response,
        session: SessionDependency,
    ) -> TransactionDraftResponse:
        result, created = decide_transaction_draft(session, draft_id, payload)
        response.status_code = 201 if created else 200
        return result

    @app.get("/v1/portfolio", response_model=PortfolioResponse)
    def portfolio_get(session: SessionDependency) -> PortfolioResponse:
        return get_portfolio(session)

    @app.get("/v1/analytics/overview", response_model=AnalyticsOverviewResponse)
    def analytics_overview_get(session: SessionDependency) -> AnalyticsOverviewResponse:
        return get_analytics_overview(session)

    @app.get("/v1/alerts", response_model=MonitorAlertListResponse)
    def alerts_get(
        session: SessionDependency,
        include_acknowledged: bool = True,
        limit: int = Query(default=100, ge=1, le=100),
    ) -> MonitorAlertListResponse:
        return list_alerts(
            session,
            include_acknowledged=include_acknowledged,
            limit=limit,
        )

    @app.post(
        "/v1/alerts/{alert_id}/acknowledgements",
        response_model=AlertAcknowledgementResponse,
        status_code=201,
    )
    def alert_acknowledgement_post(
        alert_id: UUID,
        _: AlertAcknowledgeCreate,
        response: Response,
        session: SessionDependency,
    ) -> AlertAcknowledgementResponse:
        result, created = acknowledge_alert(session, alert_id)
        response.status_code = 201 if created else 200
        return result

    @app.get("/v1/monitor-runs", response_model=MonitorRunListResponse)
    def monitor_runs_get(
        session: SessionDependency,
        limit: int = Query(default=20, ge=1, le=100),
    ) -> MonitorRunListResponse:
        return list_monitor_runs(session, limit=limit)

    @app.post("/v1/recommendations", response_model=RecommendationResponse, status_code=201)
    def recommendation_post(
        payload: RecommendationCreate, session: SessionDependency
    ) -> RecommendationResponse:
        return create_recommendation(session, payload)

    @app.post(
        "/v1/discovery/recommendations",
        response_model=RecommendationResponse,
        status_code=201,
    )
    def discovery_recommendation_post(
        payload: DiscoveryRecommendationCreate,
        session: SessionDependency,
    ) -> RecommendationResponse:
        return create_discovery_recommendation(
            session,
            payload,
            provider,
            market_research_cache_seconds=resolved.market_research_cache_seconds,
        )

    @app.post("/v1/proposal-sets", response_model=ProposalSetResponse, status_code=201)
    def proposal_set_post(
        payload: ProposalSetCreate,
        session: SessionDependency,
    ) -> ProposalSetResponse:
        return create_proposal_set(
            session,
            payload,
            provider,
            market_research_cache_seconds=resolved.market_research_cache_seconds,
        )

    @app.get("/v1/market-research/latest", response_model=MarketResearchStatusResponse)
    def market_research_latest_get(
        session: SessionDependency,
    ) -> MarketResearchStatusResponse:
        return get_latest_market_research(session)

    @app.get("/v1/proposal-sets/{proposal_set_id}", response_model=ProposalSetResponse)
    def proposal_set_get(
        proposal_set_id: UUID,
        session: SessionDependency,
    ) -> ProposalSetResponse:
        return get_proposal_set(session, proposal_set_id)

    @app.get("/v1/recommendations/{run_id}", response_model=RecommendationResponse)
    def recommendation_get(run_id: UUID, session: SessionDependency) -> RecommendationResponse:
        return get_recommendation(session, run_id)

    return app


app = create_app()
