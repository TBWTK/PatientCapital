"""Store transaction accrued interest separately from clean unit price.

Revision ID: 20260816_0002
Revises: 20260815_0001
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260816_0002"
down_revision: str | None = "20260815_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "accrued_interest_total",
            sa.Numeric(20, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_check_constraint(
        "ck_transactions_accrued_interest_total_nonnegative",
        "transactions",
        "accrued_interest_total >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_transactions_accrued_interest_total_nonnegative",
        "transactions",
        type_="check",
    )
    op.drop_column("transactions", "accrued_interest_total")
