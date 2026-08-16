"""Add immutable issuer evidence and evidence-keyed admission runs.

Revision ID: 20260816_0009
Revises: 20260816_0008
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0009"
down_revision: str | None = "20260816_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "issuer_evidence_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("asset_id", sa.String(length=64), nullable=False),
        sa.Column("isin", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_issuer_evidence_snapshots_idempotency_key"
        ),
        sa.CheckConstraint("status IN ('succeeded', 'unsupported', 'unavailable', 'invalid')"),
        sa.CheckConstraint("source_count >= 0"),
    )
    op.create_index(
        "ix_issuer_evidence_snapshots_asset_id", "issuer_evidence_snapshots", ["asset_id"]
    )
    op.execute(
        "CREATE TRIGGER issuer_evidence_snapshots_immutable BEFORE UPDATE OR DELETE ON "
        "issuer_evidence_snapshots FOR EACH ROW EXECUTE FUNCTION patientcapital_reject_mutation()"
    )

    op.drop_constraint(
        "uq_asset_admission_runs_snapshot_policy", "asset_admission_runs", type_="unique"
    )
    op.add_column(
        "asset_admission_runs",
        sa.Column(
            "issuer_evidence_set_hash",
            sa.String(length=64),
            nullable=False,
            server_default="legacy-no-issuer-evidence",
        ),
    )
    op.alter_column("asset_admission_runs", "issuer_evidence_set_hash", server_default=None)
    op.create_unique_constraint(
        "uq_asset_admission_runs_snapshot_policy_evidence",
        "asset_admission_runs",
        ["market_snapshot_id", "policy_version", "issuer_evidence_set_hash"],
    )
    op.add_column(
        "asset_admission_assessments",
        sa.Column("issuer_evidence_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_asset_admission_assessments_issuer_evidence",
        "asset_admission_assessments",
        "issuer_evidence_snapshots",
        ["issuer_evidence_snapshot_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_asset_admission_assessments_issuer_evidence",
        "asset_admission_assessments",
        type_="foreignkey",
    )
    op.drop_column("asset_admission_assessments", "issuer_evidence_snapshot_id")
    op.drop_constraint(
        "uq_asset_admission_runs_snapshot_policy_evidence",
        "asset_admission_runs",
        type_="unique",
    )
    op.drop_column("asset_admission_runs", "issuer_evidence_set_hash")
    op.create_unique_constraint(
        "uq_asset_admission_runs_snapshot_policy",
        "asset_admission_runs",
        ["market_snapshot_id", "policy_version"],
    )
    op.execute(
        "DROP TRIGGER IF EXISTS issuer_evidence_snapshots_immutable "
        "ON issuer_evidence_snapshots"
    )
    op.drop_index(
        "ix_issuer_evidence_snapshots_asset_id", table_name="issuer_evidence_snapshots"
    )
    op.drop_table("issuer_evidence_snapshots")
