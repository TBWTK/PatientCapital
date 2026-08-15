"""Create versioned portfolio authorities.

Revision ID: 20260815_0001
Revises: None
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260815_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IMMUTABLE_TABLES = (
    "profile_versions",
    "asset_versions",
    "price_snapshots",
    "transactions",
    "recommendation_runs",
)


def upgrade() -> None:
    op.create_table(
        "profile_versions",
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("investment_horizon_years", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("cash_buffer", sa.Numeric(20, 2), nullable=False),
        sa.Column("broker_name", sa.String(length=200), nullable=False),
        sa.Column("fee_rate", sa.Numeric(12, 8), nullable=False),
        sa.Column("minimum_fee", sa.Numeric(20, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("investment_horizon_years BETWEEN 1 AND 100"),
        sa.CheckConstraint("cash_buffer >= 0"),
        sa.CheckConstraint("fee_rate >= 0 AND fee_rate <= 1"),
        sa.CheckConstraint("minimum_fee >= 0"),
    )
    op.create_table(
        "assets",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_table(
        "asset_versions",
        sa.Column(
            "asset_id",
            sa.String(length=64),
            sa.ForeignKey("assets.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("lot_size", sa.Integer(), nullable=False),
        sa.Column("target_weight", sa.Numeric(12, 8), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("lot_size > 0"),
        sa.CheckConstraint("target_weight >= 0 AND target_weight <= 1"),
    )
    op.create_table(
        "price_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "asset_id",
            sa.String(length=64),
            sa.ForeignKey("assets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("price", sa.Numeric(20, 8), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_age_seconds", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("price > 0"),
        sa.CheckConstraint("max_age_seconds > 0"),
    )
    op.create_index("ix_price_snapshots_asset_id", "price_snapshots", ["asset_id"])
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "asset_id",
            sa.String(length=64),
            sa.ForeignKey("assets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("fee", sa.Numeric(20, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_transactions_idempotency_key"),
        sa.CheckConstraint("side IN ('BUY', 'SELL')"),
        sa.CheckConstraint("quantity > 0"),
        sa.CheckConstraint("unit_price > 0"),
        sa.CheckConstraint("fee >= 0"),
    )
    op.create_index("ix_transactions_asset_id", "transactions", ["asset_id"])
    op.create_table(
        "recommendation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("contribution", sa.Numeric(20, 2), nullable=False),
        sa.Column("cash_buffer", sa.Numeric(20, 2), nullable=False),
        sa.Column("gross", sa.Numeric(20, 2), nullable=False),
        sa.Column("fees", sa.Numeric(20, 2), nullable=False),
        sa.Column("spent", sa.Numeric(20, 2), nullable=False),
        sa.Column("leftover", sa.Numeric(20, 2), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_recommendation_runs_input_hash", "recommendation_runs", ["input_hash"])

    op.execute(
        """
        CREATE FUNCTION patientcapital_reject_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'immutable table % does not allow %', TG_TABLE_NAME, TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in _IMMUTABLE_TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION patientcapital_reject_mutation()"
        )


def downgrade() -> None:
    for table in reversed(_IMMUTABLE_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
    op.execute("DROP FUNCTION IF EXISTS patientcapital_reject_mutation()")
    op.drop_index("ix_recommendation_runs_input_hash", table_name="recommendation_runs")
    op.drop_table("recommendation_runs")
    op.drop_index("ix_transactions_asset_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_index("ix_price_snapshots_asset_id", table_name="price_snapshots")
    op.drop_table("price_snapshots")
    op.drop_table("asset_versions")
    op.drop_table("assets")
    op.drop_table("profile_versions")
