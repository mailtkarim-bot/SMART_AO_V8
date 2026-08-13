"""Add durable outbox retry error code for DCE retention.

Revision ID: 20260813_0012
Revises: 20260813_0011
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260813_0012"
down_revision = "20260813_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "outbox_messages",
        sa.Column("last_error_code", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("outbox_messages", "last_error_code")
