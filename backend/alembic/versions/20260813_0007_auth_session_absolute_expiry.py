"""Add absolute session expiry required by SEC-01.

Revision ID: 20260813_0007
Revises: 20260813_0006
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260813_0007"
down_revision = "20260813_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "auth_sessions",
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE auth_sessions SET absolute_expires_at = expires_at "
        "WHERE absolute_expires_at IS NULL"
    )
    op.alter_column("auth_sessions", "absolute_expires_at", nullable=False)
    op.create_check_constraint(
        op.f("ck_auth_sessions__absolute_expiry"),
        "auth_sessions",
        "absolute_expires_at > issued_at",
    )
    op.create_check_constraint(
        op.f("ck_auth_sessions__expiry_bound"),
        "auth_sessions",
        "expires_at <= absolute_expires_at",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_auth_sessions__expiry_bound"),
        "auth_sessions",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_auth_sessions__absolute_expiry"),
        "auth_sessions",
        type_="check",
    )
    op.drop_column("auth_sessions", "absolute_expires_at")
