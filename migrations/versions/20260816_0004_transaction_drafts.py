"""Add immutable transaction drafts and decisions.

Revision ID: 20260816_0004
Revises: 20260816_0003
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0004"
down_revision: str | None = "20260816_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transaction_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_kind", sa.String(length=16), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("extractor_version", sa.String(length=64), nullable=False),
        sa.Column("extracted_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("unknown_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("conflicts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("field_confidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version = 1"),
        sa.CheckConstraint("source_kind IN ('text', 'image', 'manual')"),
    )
    op.create_table(
        "transaction_draft_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "draft_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transaction_drafts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("confirmed_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transactions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("decision IN ('confirm', 'reject')"),
        sa.UniqueConstraint("draft_id", name="uq_transaction_draft_decisions_draft_id"),
    )
    op.execute(
        "CREATE TRIGGER transaction_drafts_immutable BEFORE UPDATE OR DELETE ON transaction_drafts "
        "FOR EACH ROW EXECUTE FUNCTION patientcapital_reject_mutation()"
    )
    op.execute(
        "CREATE TRIGGER transaction_draft_decisions_immutable BEFORE UPDATE OR DELETE ON "
        "transaction_draft_decisions FOR EACH ROW EXECUTE FUNCTION patientcapital_reject_mutation()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS transaction_draft_decisions_immutable "
        "ON transaction_draft_decisions"
    )
    op.execute("DROP TRIGGER IF EXISTS transaction_drafts_immutable ON transaction_drafts")
    op.drop_table("transaction_draft_decisions")
    op.drop_table("transaction_drafts")
