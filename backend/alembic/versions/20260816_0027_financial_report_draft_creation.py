"""Enforce one open financial DRAFT per tenant Case.

Revision ID: 20260816_0027
Revises: 20260816_0026
Create Date: 2026-08-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260816_0027"
down_revision = "20260816_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_financial_snapshot__tenant_case_open_draft",
        "financial_report_snapshots",
        ["tenant_id", "case_id"],
        unique=True,
        postgresql_where=sa.text("state = 'DRAFT'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_financial_snapshot__tenant_case_open_draft",
        table_name="financial_report_snapshots",
    )
