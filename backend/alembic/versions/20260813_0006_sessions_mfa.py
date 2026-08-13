"""Create SEC-01 session, refresh token and MFA persistence.

Revision ID: 20260813_0006
Revises: 20260813_0005
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260813_0006"
down_revision = "20260813_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_memberships__tenant_id_identity_id",
        "tenant_memberships",
        ["tenant_id", "id", "identity_id"],
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("auth_strength", sa.String(length=16), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mfa_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(length=64), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("state IN ('ACTIVE', 'EXPIRED', 'REVOKED')", name="state"),
        sa.CheckConstraint(
            "auth_strength IN ('PASSWORD', 'MFA', 'MFA_STEP_UP')", name="auth_strength"
        ),
        sa.CheckConstraint("token_version >= 1", name="token_version"),
        sa.CheckConstraint("expires_at > issued_at", name="expiry"),
        sa.CheckConstraint("last_seen_at >= issued_at", name="last_seen"),
        sa.CheckConstraint(
            "(auth_strength = 'PASSWORD' AND mfa_verified_at IS NULL) OR "
            "(auth_strength IN ('MFA', 'MFA_STEP_UP') AND mfa_verified_at IS NOT NULL)",
            name="mfa_verified",
        ),
        sa.CheckConstraint(
            "(state IN ('ACTIVE', 'EXPIRED') AND revoked_at IS NULL AND revoke_reason IS NULL) OR "
            "(state = 'REVOKED' AND revoked_at IS NOT NULL AND revoke_reason IS NOT NULL)",
            name="revocation",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_sessions__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "membership_id", "identity_id"],
            [
                "tenant_memberships.tenant_id",
                "tenant_memberships.id",
                "tenant_memberships.identity_id",
            ],
            name="fk_sessions__membership_identity",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_sessions__tenant_id"),
    )
    op.create_index("ix_auth_sessions_tenant_id", "auth_sessions", ["tenant_id"], unique=False)

    op.create_table(
        "refresh_token_families",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(length=64), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "state IN ('ACTIVE', 'COMPROMISED', 'REVOKED', 'EXPIRED')", name="state"
        ),
        sa.CheckConstraint("expires_at > issued_at", name="expiry"),
        sa.CheckConstraint(
            "(state IN ('ACTIVE', 'EXPIRED') AND revoked_at IS NULL AND revoke_reason IS NULL) OR "
            "(state IN ('COMPROMISED', 'REVOKED') "
            "AND revoked_at IS NOT NULL AND revoke_reason IS NOT NULL)",
            name="revocation",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_refresh_families__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "session_id"],
            ["auth_sessions.tenant_id", "auth_sessions.id"],
            name="fk_refresh_families__session",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_token_families"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_refresh_families__tenant_id"),
        sa.UniqueConstraint("tenant_id", "session_id", name="uq_refresh_families__tenant_session"),
    )
    op.create_index(
        "ix_refresh_token_families_tenant_id",
        "refresh_token_families",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_token_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("token_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("token_hash ~ '^[a-f0-9]{64}$'", name="token_hash"),
        sa.CheckConstraint("state IN ('ACTIVE', 'ROTATED', 'REVOKED', 'EXPIRED')", name="state"),
        sa.CheckConstraint("expires_at > issued_at", name="expiry"),
        sa.CheckConstraint(
            "(state IN ('ACTIVE', 'EXPIRED') AND consumed_at IS NULL AND revoked_at IS NULL) OR "
            "(state = 'ROTATED' AND consumed_at IS NOT NULL AND revoked_at IS NULL) OR "
            "(state = 'REVOKED' AND revoked_at IS NOT NULL)",
            name="lifecycle",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_refresh_tokens__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "family_id"],
            ["refresh_token_families.tenant_id", "refresh_token_families.id"],
            name="fk_refresh_tokens__family",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "parent_token_id", "family_id"],
            [
                "refresh_tokens.tenant_id",
                "refresh_tokens.id",
                "refresh_tokens.family_id",
            ],
            name="fk_refresh_tokens__parent",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_tokens"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_refresh_tokens__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "id", "family_id", name="uq_refresh_tokens__tenant_id_family"
        ),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens__token_hash"),
    )
    op.create_index("ix_refresh_tokens_tenant_id", "refresh_tokens", ["tenant_id"], unique=False)
    op.create_index(
        "ux_refresh_tokens__active_family",
        "refresh_tokens",
        ["family_id"],
        unique=True,
        postgresql_where=sa.text("state = 'ACTIVE'"),
    )

    op.create_table(
        "mfa_factors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("factor_type", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("secret_ciphertext", sa.Text(), nullable=True),
        sa.Column("encryption_key_version", sa.Integer(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("factor_type IN ('TOTP', 'RECOVERY_CODES')", name="factor_type"),
        sa.CheckConstraint("state IN ('PENDING', 'ACTIVE', 'DISABLED')", name="state"),
        sa.CheckConstraint(
            "(factor_type = 'TOTP' AND secret_ciphertext IS NOT NULL "
            "AND encryption_key_version IS NOT NULL AND encryption_key_version >= 1) OR "
            "(factor_type = 'RECOVERY_CODES' AND secret_ciphertext IS NULL "
            "AND encryption_key_version IS NULL)",
            name="secret_storage",
        ),
        sa.CheckConstraint(
            "(state = 'PENDING' AND verified_at IS NULL AND disabled_at IS NULL) OR "
            "(state = 'ACTIVE' AND verified_at IS NOT NULL AND disabled_at IS NULL) OR "
            "(state = 'DISABLED' AND disabled_at IS NOT NULL)",
            name="lifecycle",
        ),
        sa.ForeignKeyConstraint(
            ["identity_id"],
            ["identities.id"],
            name="fk_mfa_factors__identity",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mfa_factors"),
        sa.UniqueConstraint("identity_id", "id", name="uq_mfa_factors__identity_id"),
        sa.UniqueConstraint(
            "identity_id", "id", "factor_type", name="uq_mfa_factors__identity_id_type"
        ),
    )
    op.create_index(
        "ux_mfa_factors__active_totp",
        "mfa_factors",
        ["identity_id"],
        unique=True,
        postgresql_where=sa.text("factor_type = 'TOTP' AND state = 'ACTIVE'"),
    )

    op.create_table(
        "mfa_recovery_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("factor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("factor_type", sa.String(length=16), nullable=False),
        sa.Column("code_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("code_hash ~ '^[a-f0-9]{64}$'", name="code_hash"),
        sa.CheckConstraint("factor_type = 'RECOVERY_CODES'", name="factor_type"),
        sa.ForeignKeyConstraint(
            ["identity_id"],
            ["identities.id"],
            name="fk_mfa_recovery_codes__identity",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["identity_id", "factor_id", "factor_type"],
            [
                "mfa_factors.identity_id",
                "mfa_factors.id",
                "mfa_factors.factor_type",
            ],
            name="fk_mfa_recovery_codes__factor",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mfa_recovery_codes"),
        sa.UniqueConstraint("code_hash", name="uq_mfa_recovery_codes__code_hash"),
    )


def downgrade() -> None:
    op.drop_table("mfa_recovery_codes")
    op.drop_index("ux_mfa_factors__active_totp", table_name="mfa_factors")
    op.drop_table("mfa_factors")
    op.drop_index("ux_refresh_tokens__active_family", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_tenant_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_refresh_token_families_tenant_id", table_name="refresh_token_families")
    op.drop_table("refresh_token_families")
    op.drop_index("ix_auth_sessions_tenant_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_constraint(
        "uq_memberships__tenant_id_identity_id",
        "tenant_memberships",
        type_="unique",
    )
