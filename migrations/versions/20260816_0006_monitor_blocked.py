"""Admit explicit blocked monitor outcomes.

Revision ID: 20260816_0006
Revises: 20260816_0005
Create Date: 2026-08-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260816_0006"
down_revision: str | None = "20260816_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("monitor_runs_status_check", "monitor_runs", type_="check")
    op.create_check_constraint(
        "monitor_runs_status_check",
        "monitor_runs",
        "status IN ('no_change', 'alerts_created', 'provider_error', 'blocked')",
    )


def downgrade() -> None:
    op.drop_constraint("monitor_runs_status_check", "monitor_runs", type_="check")
    op.create_check_constraint(
        "monitor_runs_status_check",
        "monitor_runs",
        "status IN ('no_change', 'alerts_created', 'provider_error')",
    )
