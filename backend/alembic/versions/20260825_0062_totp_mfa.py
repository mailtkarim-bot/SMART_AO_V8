"""Add encrypted TOTP factors and one-time recovery codes.

Revision ID: 20260825_0062
Revises: 20260825_0061
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260825_0062"
down_revision = "20260825_0061"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_UUID = postgresql.UUID(as_uuid=True)
_EVENT_TYPE_CONSTRAINT = (
    "event_type IN ("
    "'AUTH_LOGIN_SUCCEEDED', 'AUTH_LOGIN_DENIED', "
    "'AUTH_REFRESH_SUCCEEDED', 'AUTH_REFRESH_DENIED', "
    "'AUTH_LOGOUT_SUCCEEDED', 'AUTH_SESSION_REJECTED', "
    "'AUTHZ_SUCCEEDED', 'AUTHZ_DENIED', 'AUTHZ_STEP_UP_REQUIRED', "
    "'AUTH_MFA_ENROLLMENT_STARTED', 'AUTH_MFA_ENROLLMENT_CONFIRMED', "
    "'AUTH_MFA_VERIFICATION_DENIED', 'AUTH_MFA_STEP_UP_SUCCEEDED', "
    "'AUTH_MFA_RECOVERY_USED', 'AUTH_MFA_DISABLED', "
    "'SUBMISSION_PACKAGE_EXPORTED'"
    ")"
)
_PREVIOUS_EVENT_TYPE_CONSTRAINT = (
    "event_type IN ("
    "'AUTH_LOGIN_SUCCEEDED', 'AUTH_LOGIN_DENIED', "
    "'AUTH_REFRESH_SUCCEEDED', 'AUTH_REFRESH_DENIED', "
    "'AUTH_LOGOUT_SUCCEEDED', 'AUTH_SESSION_REJECTED', "
    "'AUTHZ_SUCCEEDED', 'AUTHZ_DENIED', 'AUTHZ_STEP_UP_REQUIRED', "
    "'SUBMISSION_PACKAGE_EXPORTED'"
    ")"
)


def upgrade() -> None:
    op.create_table(
        "mfa_totp_factors",
        sa.Column("id", _UUID, nullable=False),
        sa.Column("identity_id", _UUID, nullable=False),
        sa.Column("encrypted_secret", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_step", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["identity_id"], ["identities.id"], name="fk_mfa_totp__identity", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", name="uq_mfa_totp__id"),
        sa.CheckConstraint("state IN ('PENDING', 'ACTIVE', 'DISABLED')", name="state"),
        sa.CheckConstraint("length(encrypted_secret) >= 80", name="encrypted_secret"),
        sa.CheckConstraint("expires_at > created_at", name="expiry"),
        sa.CheckConstraint(
            "(state = 'PENDING' AND confirmed_at IS NULL) OR "
            "(state IN ('ACTIVE', 'DISABLED') AND confirmed_at IS NOT NULL)",
            name="confirmation",
        ),
    )
    op.create_index(
        "ux_mfa_totp__active_identity",
        "mfa_totp_factors",
        ["identity_id"],
        unique=True,
        postgresql_where=sa.text("state = 'ACTIVE'"),
    )
    op.create_table(
        "mfa_totp_recovery_codes",
        sa.Column("id", _UUID, nullable=False),
        sa.Column("factor_id", _UUID, nullable=False),
        sa.Column("code_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["factor_id"],
            ["mfa_totp_factors.id"],
            name="fk_mfa_recovery__factor",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", name="uq_mfa_recovery__id"),
        sa.UniqueConstraint("factor_id", "code_hash", name="uq_mfa_recovery__factor_hash"),
        sa.CheckConstraint("code_hash ~ '^[a-f0-9]{64}$'", name="code_hash"),
    )
    op.drop_constraint("event_type", "security_audit_events", type_="check")
    op.create_check_constraint("event_type", "security_audit_events", _EVENT_TYPE_CONSTRAINT)


def downgrade() -> None:
    op.drop_constraint("event_type", "security_audit_events", type_="check")
    op.create_check_constraint(
        "event_type", "security_audit_events", _PREVIOUS_EVENT_TYPE_CONSTRAINT
    )
    op.drop_table("mfa_totp_recovery_codes")
    op.drop_index("ux_mfa_totp__active_identity", table_name="mfa_totp_factors")
    op.drop_table("mfa_totp_factors")
