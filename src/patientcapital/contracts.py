"""Versioned API contracts shared by HTTP and future agent adapters."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProfilePut(ContractModel):
    expected_version: int | None = Field(default=None, ge=1)
    base_currency: str = Field(pattern=r"^[A-Z]{3}$")
    investment_horizon_years: int = Field(ge=1, le=100)
    risk_level: Literal["conservative", "balanced", "growth"]
    cash_buffer: Decimal = Field(ge=0, decimal_places=2)
    broker_name: str = Field(min_length=1, max_length=200)
    fee_rate: Decimal = Field(ge=0, le=1, decimal_places=8)
    minimum_fee: Decimal = Field(ge=0, decimal_places=2)


class ProfileResponse(ContractModel):
    version: int
    base_currency: str
    investment_horizon_years: int
    risk_level: str
    cash_buffer: Decimal
    broker_name: str
    fee_rate: Decimal
    minimum_fee: Decimal
    created_at: datetime


class AssetPut(ContractModel):
    expected_version: int | None = Field(default=None, ge=1)
    name: str = Field(min_length=1, max_length=200)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    lot_size: int = Field(gt=0)
    target_weight: Decimal = Field(ge=0, le=1, decimal_places=8)
    is_active: bool = True


class AssetResponse(ContractModel):
    asset_id: str
    version: int
    name: str
    currency: str
    lot_size: int
    target_weight: Decimal
    is_active: bool
    created_at: datetime


class AssetListResponse(ContractModel):
    assets: list[AssetResponse]


class PriceCreate(ContractModel):
    price: Decimal = Field(gt=0, decimal_places=8)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    as_of: datetime
    max_age_seconds: int = Field(gt=0, le=31_536_000)
    source: str = Field(min_length=1, max_length=200)


class PriceResponse(ContractModel):
    id: UUID
    asset_id: str
    price: Decimal
    currency: str
    as_of: datetime
    max_age_seconds: int
    source: str
    created_at: datetime


class TransactionCreate(ContractModel):
    idempotency_key: str = Field(min_length=1, max_length=128)
    asset_id: str = Field(min_length=1, max_length=64)
    side: Literal["BUY", "SELL"]
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0, decimal_places=8)
    accrued_interest_total: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    fee: Decimal = Field(ge=0, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    occurred_at: AwareDatetime
    note: str | None = Field(default=None, max_length=2000)


class TransactionResponse(ContractModel):
    id: UUID
    idempotency_key: str
    asset_id: str
    side: str
    quantity: int
    unit_price: Decimal
    accrued_interest_total: Decimal
    fee: Decimal
    currency: str
    occurred_at: datetime
    note: str | None
    created_at: datetime


class TransactionDraftTextCreate(ContractModel):
    text: str = Field(min_length=2, max_length=100_000)


class TransactionDraftFields(ContractModel):
    side: Literal["BUY", "SELL"] | None = None
    asset_id: str | None = None
    asset_name: str | None = None
    quantity: int | None = None
    unit_price: Decimal | None = None
    accrued_interest_total: Decimal | None = None
    fee: Decimal | None = None
    currency: str | None = None
    occurred_at: datetime | None = None


class TransactionDraftManualCreate(ContractModel):
    asset_id: str = Field(min_length=1, max_length=64)
    side: Literal["BUY", "SELL"]
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0, decimal_places=8)
    accrued_interest_total: Decimal = Field(ge=0, decimal_places=2)
    fee: Decimal = Field(ge=0, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    occurred_at: AwareDatetime
    note: str | None = Field(default=None, max_length=2000)


class TransactionDraftDecisionCreate(ContractModel):
    expected_version: int = Field(ge=1)
    decision: Literal["confirm", "reject"]
    transaction: TransactionCreate | None = None

    @model_validator(mode="after")
    def validate_decision_payload(self) -> "TransactionDraftDecisionCreate":
        if self.decision == "confirm" and self.transaction is None:
            raise ValueError("confirmed draft requires an exact transaction payload")
        if self.decision == "reject" and self.transaction is not None:
            raise ValueError("rejected draft cannot include a transaction payload")
        return self


class TransactionDraftDecisionResponse(ContractModel):
    decision: Literal["confirm", "reject"]
    transaction: TransactionResponse | None
    decided_at: datetime


class TransactionDraftResponse(ContractModel):
    id: UUID
    version: int
    status: Literal["unconfirmed", "confirmed", "rejected"]
    source_kind: Literal["text", "image", "manual"]
    source_sha256: str
    source_metadata: dict[str, str | int]
    extractor_version: str
    fields: TransactionDraftFields
    unknown_fields: list[str]
    conflicts: list[str]
    field_confidence: dict[str, Decimal]
    created_at: datetime
    expires_at: datetime
    decision: TransactionDraftDecisionResponse | None


class PortfolioAssetResponse(ContractModel):
    asset_id: str
    name: str
    quantity: int
    currency: str
    latest_price: Decimal
    price_as_of: datetime
    market_value: Decimal
    cost_basis: Decimal
    unrealized_pnl: Decimal
    target_weight: Decimal
    actual_weight: Decimal
    drift: Decimal


class PortfolioResponse(ContractModel):
    currency: str
    total_market_value: Decimal
    total_cost_basis: Decimal
    total_unrealized_pnl: Decimal
    assets: list[PortfolioAssetResponse]


class AnalyticsMoneyMetricResponse(ContractModel):
    status: Literal["available", "unknown", "not_configured"]
    value: Decimal | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_metric_state(self) -> "AnalyticsMoneyMetricResponse":
        if self.status == "available" and self.value is None:
            raise ValueError("available analytics metric requires a value")
        if self.status != "available" and (self.value is not None or self.reason is None):
            raise ValueError("unavailable analytics metric requires only a reason")
        return self


class PriceFreshnessAssetResponse(ContractModel):
    asset_id: str
    status: Literal["fresh", "stale"]
    as_of: datetime
    max_age_seconds: int
    source: str


class PriceFreshnessResponse(ContractModel):
    status: Literal["fresh", "stale", "unknown"]
    oldest_as_of: datetime | None
    reason: str | None
    assets: list[PriceFreshnessAssetResponse]


class AnalyticsOverviewResponse(ContractModel):
    currency: str
    calculated_at: datetime
    algorithm_version: str
    market_value: AnalyticsMoneyMetricResponse
    cost_basis: AnalyticsMoneyMetricResponse
    net_contributions: AnalyticsMoneyMetricResponse
    realized_result: AnalyticsMoneyMetricResponse
    unrealized_result: AnalyticsMoneyMetricResponse
    income: AnalyticsMoneyMetricResponse
    price_freshness: PriceFreshnessResponse
    allocation: list[PortfolioAssetResponse]
    recent_activity: list[TransactionResponse]


class RecommendationCreate(ContractModel):
    contribution: Decimal = Field(ge=0, decimal_places=2)


class DiscoveryRecommendationCreate(ContractModel):
    contribution: Decimal = Field(gt=0, decimal_places=2)


class ResearchCitationResponse(ContractModel):
    kind: Literal["fundamentals", "dividends", "governance", "corporate_actions"]
    title: str
    url: str


class DividendResearchResponse(ContractModel):
    schema_version: str
    policy_version: str
    observed_at: datetime
    max_age_seconds: int
    reporting_period_end: date
    profitable_years: int
    dividend_years: int
    payout_ratio_percent: Decimal
    balance_sheet_status: Literal["no_debt", "adequate_capital", "concern", "unknown"]
    governance_program_member: bool
    corporate_action_status: Literal[
        "no_material_action_identified", "material", "unknown"
    ]
    summary: str
    citations: list[ResearchCitationResponse]


class DiscoveryCandidateResponse(ContractModel):
    asset_id: str
    name: str
    instrument_type: Literal["ofz", "equity_index_fund", "dividend_stock"]
    target_weight: Decimal
    rationale: str
    unit_price: Decimal
    lot_size: int
    lot_cost: Decimal
    price_as_of: datetime
    quote_kind: str
    turnover: Decimal
    maturity_date: date | None = None
    yield_percent: Decimal | None = None
    source_url: str
    classification_url: str
    research: DividendResearchResponse | None = None


class RejectedDiscoveryCandidateResponse(ContractModel):
    asset_id: str
    name: str
    instrument_type: Literal["ofz", "equity_index_fund", "dividend_stock"]
    reason: str
    unit_price: Decimal
    lot_size: int
    lot_cost: Decimal
    price_as_of: datetime
    source_url: str


class RecommendationLineResponse(ContractModel):
    asset_id: str
    lots: int
    lot_size: int
    quantity: int
    unit_price: Decimal
    current_value: Decimal
    target_value: Decimal
    pre_drift: Decimal
    post_drift: Decimal
    gross: Decimal
    fee: Decimal
    total: Decimal


class RecommendationResponse(ContractModel):
    id: UUID
    algorithm_version: str
    input_hash: str
    calculated_at: datetime
    currency: str
    contribution: Decimal
    cash_buffer: Decimal
    investable: Decimal
    gross: Decimal
    fees: Decimal
    spent: Decimal
    leftover: Decimal
    reason: str
    lines: list[RecommendationLineResponse]
    mode: Literal["manual", "automatic"] = "manual"
    policy_version: str | None = None
    horizon_years: int | None = None
    risk_level: str | None = None
    candidates: list[DiscoveryCandidateResponse] = Field(default_factory=list)
    rejected_candidates: list[RejectedDiscoveryCandidateResponse] = Field(default_factory=list)
    profile_version: int | None = None


class ProposalSetCreate(ContractModel):
    contribution: Decimal = Field(gt=0, decimal_places=2)


class StrategyProposalResponse(ContractModel):
    strategy_id: str
    name: str
    summary: str
    why: str
    risk_note: str
    tradeoffs: list[str]
    recommended: bool
    recommendation: RecommendationResponse


class ProposalSetResponse(ContractModel):
    id: UUID
    contribution: Decimal
    currency: str
    profile_version: int
    recommended_strategy_id: str
    strategies: list[StrategyProposalResponse] = Field(min_length=1, max_length=3)
    created_at: datetime


class ErrorDetail(ContractModel):
    code: str
    message: str


class ErrorResponse(ContractModel):
    error: ErrorDetail
