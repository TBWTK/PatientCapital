"""Add immutable assistant-first proposal sets.

Revision ID: 20260816_0003
Revises: 20260816_0002
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0003"
down_revision: str | None = "20260816_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "proposal_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contribution", sa.Numeric(20, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "profile_version",
            sa.Integer(),
            sa.ForeignKey("profile_versions.version", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("recommended_strategy_id", sa.String(length=64), nullable=False),
        sa.Column("strategies", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("contribution > 0"),
    )
    op.execute(
        "CREATE TRIGGER proposal_sets_immutable BEFORE UPDATE OR DELETE ON proposal_sets "
        "FOR EACH ROW EXECUTE FUNCTION patientcapital_reject_mutation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS proposal_sets_immutable ON proposal_sets")
    op.drop_table("proposal_sets")
