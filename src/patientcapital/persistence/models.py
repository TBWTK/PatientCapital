"""SQLAlchemy mappings; tables are authorities, projections remain derived."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProfileVersion(Base):
    __tablename__ = "profile_versions"
    __table_args__ = (
        CheckConstraint("investment_horizon_years BETWEEN 1 AND 100"),
        CheckConstraint("cash_buffer >= 0"),
        CheckConstraint("fee_rate >= 0 AND fee_rate <= 1"),
        CheckConstraint("minimum_fee >= 0"),
    )

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    investment_horizon_years: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    cash_buffer: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    broker_name: Mapped[str] = mapped_column(String(200), nullable=False)
    fee_rate: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    minimum_fee: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AssetIdentity(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AssetVersion(Base):
    __tablename__ = "asset_versions"
    __table_args__ = (
        CheckConstraint("lot_size > 0"),
        CheckConstraint("target_weight >= 0 AND target_weight <= 1"),
    )

    asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    lot_size: Mapped[int] = mapped_column(Integer, nullable=False)
    target_weight: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PriceRecord(Base):
    __tablename__ = "price_snapshots"
    __table_args__ = (
        CheckConstraint("price > 0"),
        CheckConstraint("max_age_seconds > 0"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_age_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TransactionRecord(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_transactions_idempotency_key"),
        CheckConstraint("side IN ('BUY', 'SELL')"),
        CheckConstraint("quantity > 0"),
        CheckConstraint("unit_price > 0"),
        CheckConstraint("accrued_interest_total >= 0"),
        CheckConstraint("fee >= 0"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    accrued_interest_total: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False, server_default="0"
    )
    fee: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RecommendationRunRecord(Base):
    __tablename__ = "recommendation_runs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    contribution: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    cash_buffer: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    gross: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    fees: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    spent: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    leftover: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    input_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    output_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProposalSetRecord(Base):
    __tablename__ = "proposal_sets"
    __table_args__ = (CheckConstraint("contribution > 0"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    contribution: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    profile_version: Mapped[int] = mapped_column(
        ForeignKey("profile_versions.version", ondelete="RESTRICT"), nullable=False
    )
    recommended_strategy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    strategies: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MarketResearchSnapshotRecord(Base):
    __tablename__ = "market_research_snapshots"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_market_research_snapshots_idempotency_key"),
        CheckConstraint("status IN ('succeeded', 'provider_error')"),
        CheckConstraint("universe_size >= 0"),
        CheckConstraint("candidate_count >= 0 AND candidate_count <= universe_size"),
        CheckConstraint("enriched_count >= 0"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    scan_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    universe_size: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    enriched_count: Mapped[int] = mapped_column(Integer, nullable=False)
    kind_counts: Mapped[dict[str, int]] = mapped_column(JSONB, nullable=False)
    candidates: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AssetAdmissionRunRecord(Base):
    __tablename__ = "asset_admission_runs"
    __table_args__ = (
        UniqueConstraint(
            "market_snapshot_id",
            "policy_version",
            "issuer_evidence_set_hash",
            name="uq_asset_admission_runs_snapshot_policy_evidence",
        ),
        CheckConstraint("scope IN ('universe_discovery', 'pool_refresh', 'on_demand')"),
        CheckConstraint("status = 'succeeded'"),
        CheckConstraint("assessment_count >= 0"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    market_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("market_research_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    issuer_evidence_set_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assessment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status_counts: Mapped[dict[str, int]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AssetAdmissionAssessmentRecord(Base):
    __tablename__ = "asset_admission_assessments"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "asset_id",
            "policy_version",
            name="uq_asset_admission_assessments_run_asset_policy",
        ),
        CheckConstraint("overall_status IN ('eligible', 'watch', 'reject', 'unknown')"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("asset_admission_runs.id", ondelete="RESTRICT"), nullable=False
    )
    issuer_evidence_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("issuer_evidence_snapshots.id", ondelete="RESTRICT"), nullable=True
    )
    asset_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    instrument_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    strategy_profile: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    overall_status: Mapped[str] = mapped_column(String(16), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    profile: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IssuerEvidenceSnapshotRecord(Base):
    __tablename__ = "issuer_evidence_snapshots"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_issuer_evidence_snapshots_idempotency_key"),
        CheckConstraint("status IN ('succeeded', 'unsupported', 'unavailable', 'invalid')"),
        CheckConstraint("source_count >= 0"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    isin: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TransactionDraftRecord(Base):
    __tablename__ = "transaction_drafts"
    __table_args__ = (
        CheckConstraint("version = 1"),
        CheckConstraint("source_kind IN ('text', 'image', 'manual')"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(64), nullable=False)
    extracted_fields: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    unknown_fields: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    conflicts: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    field_confidence: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TransactionDraftDecisionRecord(Base):
    __tablename__ = "transaction_draft_decisions"
    __table_args__ = (
        UniqueConstraint("draft_id", name="uq_transaction_draft_decisions_draft_id"),
        CheckConstraint("decision IN ('confirm', 'reject')"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    draft_id: Mapped[UUID] = mapped_column(
        ForeignKey("transaction_drafts.id", ondelete="RESTRICT"), nullable=False
    )
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    confirmed_payload: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    transaction_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MonitorRunRecord(Base):
    __tablename__ = "monitor_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_monitor_runs_idempotency_key"),
        CheckConstraint("status IN ('no_change', 'alerts_created', 'provider_error', 'blocked')"),
        CheckConstraint("alerts_created >= 0"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    alerts_created: Mapped[int] = mapped_column(Integer, nullable=False)
    input_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    result_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MonitorAlertRecord(Base):
    __tablename__ = "monitor_alerts"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_monitor_alerts_dedupe_key"),
        CheckConstraint(
            "kind IN ('allocation_drift', 'price_move', 'research_expiring', "
            "'corporate_action_review')"
        ),
        CheckConstraint("severity IN ('info', 'warning')"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    monitor_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("monitor_runs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MonitorAlertAcknowledgementRecord(Base):
    __tablename__ = "monitor_alert_acknowledgements"
    __table_args__ = (
        UniqueConstraint("alert_id", name="uq_monitor_alert_acknowledgements_alert_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    alert_id: Mapped[UUID] = mapped_column(
        ForeignKey("monitor_alerts.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
