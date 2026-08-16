"""Add immutable monitor runs, alerts, and acknowledgements.

Revision ID: 20260816_0005
Revises: 20260816_0004
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0005"
down_revision: str | None = "20260816_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "monitor_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("alerts_created", sa.Integer(), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("status IN ('no_change', 'alerts_created', 'provider_error')"),
        sa.CheckConstraint("alerts_created >= 0"),
        sa.UniqueConstraint("idempotency_key", name="uq_monitor_runs_idempotency_key"),
    )
    op.create_table(
        "monitor_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "monitor_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("monitor_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("dedupe_key", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column(
            "asset_id",
            sa.String(length=64),
            sa.ForeignKey("assets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "kind IN ('allocation_drift', 'price_move', 'research_expiring', "
            "'corporate_action_review')"
        ),
        sa.CheckConstraint("severity IN ('info', 'warning')"),
        sa.UniqueConstraint("dedupe_key", name="uq_monitor_alerts_dedupe_key"),
    )
    op.create_index("ix_monitor_alerts_monitor_run_id", "monitor_alerts", ["monitor_run_id"])
    op.create_index("ix_monitor_alerts_asset_id", "monitor_alerts", ["asset_id"])
    op.create_table(
        "monitor_alert_acknowledgements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "alert_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("monitor_alerts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("alert_id", name="uq_monitor_alert_acknowledgements_alert_id"),
    )
    for table in ("monitor_runs", "monitor_alerts", "monitor_alert_acknowledgements"):
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION patientcapital_reject_mutation()"
        )


def downgrade() -> None:
    for table in ("monitor_alert_acknowledgements", "monitor_alerts", "monitor_runs"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
    op.drop_table("monitor_alert_acknowledgements")
    op.drop_index("ix_monitor_alerts_asset_id", table_name="monitor_alerts")
    op.drop_index("ix_monitor_alerts_monitor_run_id", table_name="monitor_alerts")
    op.drop_table("monitor_alerts")
    op.drop_table("monitor_runs")
