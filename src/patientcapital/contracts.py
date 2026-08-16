"""Versioned API contracts shared by HTTP and future agent adapters."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
    occurred_at: datetime
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


class RecommendationCreate(ContractModel):
    contribution: Decimal = Field(ge=0, decimal_places=2)


class DiscoveryRecommendationCreate(ContractModel):
    contribution: Decimal = Field(gt=0, decimal_places=2)


class DiscoveryCandidateResponse(ContractModel):
    asset_id: str
    name: str
    instrument_type: Literal["ofz", "equity_index_fund"]
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


class RejectedDiscoveryCandidateResponse(ContractModel):
    asset_id: str
    name: str
    instrument_type: Literal["ofz", "equity_index_fund"]
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
