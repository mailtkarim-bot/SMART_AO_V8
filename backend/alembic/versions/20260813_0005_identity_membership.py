"""Create SEC-01 identity, membership and bootstrap persistence.

Revision ID: 20260813_0005
Revises: 20260813_0004
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260813_0005"
down_revision = "20260813_0004"
branch_labels = None
depends_on = None


identity_lifecycle = (
    "'PENDING_VERIFICATION', 'ACTIVE', 'SUSPENDED', 'LOCKED', 'ARCHIVED'"
)
membership_roles = (
    "'PATRON_ADMIN', 'PATRON_DELEGATE', 'COLLABORATEUR', "
    "'PARTENAIRE_EXTERNAL', 'SUPPORT_BREAK_GLASS', 'SYSTEM'"
)
membership_states = "'INVITED', 'ACTIVE', 'SUSPENDED', 'REVOKED', 'EXPIRED'"


def upgrade() -> None:
    op.create_table(
        "identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email_normalized", sa.String(length=320), nullable=False),
        sa.Column("lifecycle", sa.String(length=32), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
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
            "email_normalized = lower(email_normalized) AND length(trim(email_normalized)) > 0",
            name="email_normalized",
        ),
        sa.CheckConstraint(
            f"lifecycle IN ({identity_lifecycle})",
            name="lifecycle",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_identities"),
        sa.UniqueConstraint("email_normalized", name="uq_identities__email_normalized"),
    )

    op.create_table(
        "password_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("algorithm", sa.String(length=32), nullable=False),
        sa.Column("parameters_version", sa.Integer(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "must_change",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
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
            "algorithm = 'ARGON2ID' AND password_hash LIKE '$argon2id$%'",
            name="argon2id",
        ),
        sa.CheckConstraint(
            "parameters_version >= 1",
            name="parameters_version",
        ),
        sa.ForeignKeyConstraint(
            ["identity_id"],
            ["identities.id"],
            name="fk_pwdcred__identity",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_password_credentials"),
        sa.UniqueConstraint("identity_id", name="uq_pwdcred__identity"),
    )

    op.create_table(
        "tenant_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            f"role IN ({membership_roles})",
            name="role",
        ),
        sa.CheckConstraint(
            f"state IN ({membership_states})",
            name="state",
        ),
        sa.CheckConstraint(
            "(state = 'INVITED' AND activated_at IS NULL AND revoked_at IS NULL) OR "
            "(state IN ('ACTIVE', 'SUSPENDED', 'EXPIRED') "
            "AND activated_at IS NOT NULL AND revoked_at IS NULL) OR "
            "(state = 'REVOKED' AND revoked_at IS NOT NULL)",
            name="timestamps",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_memberships__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["identity_id"],
            ["identities.id"],
            name="fk_memberships__identity",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tenant_memberships"),
        sa.UniqueConstraint(
            "tenant_id",
            "identity_id",
            name="uq_memberships__tenant_identity",
        ),
    )
    op.create_index(
        "ix_tenant_memberships_tenant_id",
        "tenant_memberships",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ux_memberships__active_patron",
        "tenant_memberships",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("role = 'PATRON_ADMIN' AND state = 'ACTIVE'"),
    )

    op.create_table(
        "tenant_bootstrap_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
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
            "token_hash ~ '^[a-f0-9]{64}$'",
            name="token_hash",
        ),
        sa.CheckConstraint(
            "expires_at > issued_at",
            name="expiry",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_bootstrap__tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tenant_bootstrap_tokens"),
        sa.UniqueConstraint("tenant_id", name="uq_bootstrap__tenant"),
        sa.UniqueConstraint("token_hash", name="uq_bootstrap__token_hash"),
    )
    op.create_index(
        "ix_tenant_bootstrap_tokens_tenant_id",
        "tenant_bootstrap_tokens",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_bootstrap_tokens_tenant_id", table_name="tenant_bootstrap_tokens")
    op.drop_table("tenant_bootstrap_tokens")
    op.drop_index("ux_memberships__active_patron", table_name="tenant_memberships")
    op.drop_index("ix_tenant_memberships_tenant_id", table_name="tenant_memberships")
    op.drop_table("tenant_memberships")
    op.drop_table("password_credentials")
    op.drop_table("identities")
