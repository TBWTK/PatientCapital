"""Add immutable market research snapshots.

Revision ID: 20260816_0007
Revises: 20260816_0006
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0007"
down_revision: str | None = "20260816_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_research_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("scan_policy_version", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("universe_size", sa.Integer(), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("enriched_count", sa.Integer(), nullable=False),
        sa.Column("kind_counts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("candidates", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_market_research_snapshots_idempotency_key"
        ),
        sa.CheckConstraint("status IN ('succeeded', 'provider_error')"),
        sa.CheckConstraint("universe_size >= 0"),
        sa.CheckConstraint("candidate_count >= 0 AND candidate_count <= universe_size"),
        sa.CheckConstraint("enriched_count >= 0"),
    )
    op.create_index(
        "ix_market_research_snapshots_observed_at",
        "market_research_snapshots",
        ["observed_at"],
    )
    op.execute(
        "CREATE TRIGGER market_research_snapshots_immutable BEFORE UPDATE OR DELETE ON "
        "market_research_snapshots FOR EACH ROW EXECUTE FUNCTION patientcapital_reject_mutation()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS market_research_snapshots_immutable "
        "ON market_research_snapshots"
    )
    op.drop_index(
        "ix_market_research_snapshots_observed_at",
        table_name="market_research_snapshots",
    )
    op.drop_table("market_research_snapshots")
