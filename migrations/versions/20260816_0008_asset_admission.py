"""Add immutable asset-admission runs and assessments.

Revision ID: 20260816_0008
Revises: 20260816_0007
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0008"
down_revision: str | None = "20260816_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "asset_admission_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "market_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("market_research_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assessment_count", sa.Integer(), nullable=False),
        sa.Column(
            "status_counts", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "market_snapshot_id",
            "policy_version",
            name="uq_asset_admission_runs_snapshot_policy",
        ),
        sa.CheckConstraint("scope IN ('universe_discovery', 'pool_refresh', 'on_demand')"),
        sa.CheckConstraint("status = 'succeeded'"),
        sa.CheckConstraint("assessment_count >= 0"),
    )
    op.create_index(
        "ix_asset_admission_runs_evaluated_at",
        "asset_admission_runs",
        ["evaluated_at"],
    )
    op.create_table(
        "asset_admission_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("asset_admission_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("asset_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("instrument_kind", sa.String(length=32), nullable=False),
        sa.Column("strategy_profile", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("overall_status", sa.String(length=16), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("profile", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "run_id",
            "asset_id",
            "policy_version",
            name="uq_asset_admission_assessments_run_asset_policy",
        ),
        sa.CheckConstraint("overall_status IN ('eligible', 'watch', 'reject', 'unknown')"),
    )
    op.create_index(
        "ix_asset_admission_assessments_asset_status",
        "asset_admission_assessments",
        ["asset_id", "overall_status"],
    )
    op.execute(
        "CREATE TRIGGER asset_admission_runs_immutable BEFORE UPDATE OR DELETE ON "
        "asset_admission_runs FOR EACH ROW EXECUTE FUNCTION patientcapital_reject_mutation()"
    )
    op.execute(
        "CREATE TRIGGER asset_admission_assessments_immutable BEFORE UPDATE OR DELETE ON "
        "asset_admission_assessments FOR EACH ROW EXECUTE FUNCTION patientcapital_reject_mutation()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS asset_admission_assessments_immutable "
        "ON asset_admission_assessments"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS asset_admission_runs_immutable ON asset_admission_runs"
    )
    op.drop_index(
        "ix_asset_admission_assessments_asset_status",
        table_name="asset_admission_assessments",
    )
    op.drop_table("asset_admission_assessments")
    op.drop_index(
        "ix_asset_admission_runs_evaluated_at", table_name="asset_admission_runs"
    )
    op.drop_table("asset_admission_runs")
