"""Persist exact BTP cost-basis outputs on private pricing scenarios.

Revision ID: 20260824_0057
Revises: 20260824_0056
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260824_0057"
down_revision = "20260824_0056"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_COLUMNS = (
    ("penalty_reserve_minor", sa.BigInteger()),
    ("retention_reserve_minor", sa.BigInteger()),
    ("guarantee_reserve_minor", sa.BigInteger()),
    ("floor_margin_rate_bps", sa.Integer()),
    ("target_margin_rate_bps", sa.Integer()),
    ("break_even_sales_minor", sa.BigInteger()),
    ("floor_sales_minor", sa.BigInteger()),
    ("target_sales_minor", sa.BigInteger()),
)


def upgrade() -> None:
    for name, column_type in _COLUMNS:
        op.add_column(
            "pricing_scenarios",
            sa.Column(name, column_type, nullable=False, server_default=sa.text("0")),
        )
        op.alter_column("pricing_scenarios", name, server_default=None)
    op.create_check_constraint(
        "cost_basis_reserves_non_negative",
        "pricing_scenarios",
        "penalty_reserve_minor >= 0 AND retention_reserve_minor >= 0 "
        "AND guarantee_reserve_minor >= 0",
    )
    op.create_check_constraint(
        "cost_basis_rates_valid",
        "pricing_scenarios",
        "floor_margin_rate_bps >= 0 AND floor_margin_rate_bps < 10000 "
        "AND target_margin_rate_bps >= 0 AND target_margin_rate_bps < 10000 "
        "AND floor_margin_rate_bps <= target_margin_rate_bps",
    )
    op.create_check_constraint(
        "cost_basis_thresholds_non_negative",
        "pricing_scenarios",
        "break_even_sales_minor >= 0 AND floor_sales_minor >= 0 AND target_sales_minor >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("cost_basis_thresholds_non_negative", "pricing_scenarios", type_="check")
    op.drop_constraint("cost_basis_rates_valid", "pricing_scenarios", type_="check")
    op.drop_constraint(
        "cost_basis_reserves_non_negative", "pricing_scenarios", type_="check"
    )
    for name, _ in reversed(_COLUMNS):
        op.drop_column("pricing_scenarios", name)
