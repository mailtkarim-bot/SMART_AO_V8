"""Create append-only SEC-01 security audit journal.

Revision ID: 20260813_0009
Revises: 20260813_0008
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260813_0009"
down_revision = "20260813_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "security_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("identity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_kind", sa.String(length=32), nullable=True),
        sa.Column("auth_strength", sa.String(length=16), nullable=True),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_ip_hash", sa.CHAR(length=64), nullable=True),
        sa.Column("user_agent_family", sa.String(length=120), nullable=True),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint("schema_version >= 1", name="schema_version"),
        sa.CheckConstraint(
            "event_type IN ("
            "'AUTH_LOGIN_SUCCEEDED', 'AUTH_LOGIN_DENIED', "
            "'AUTH_REFRESH_SUCCEEDED', 'AUTH_REFRESH_DENIED', "
            "'AUTH_LOGOUT_SUCCEEDED', 'AUTH_SESSION_REJECTED', "
            "'AUTHZ_DENIED', 'AUTHZ_STEP_UP_REQUIRED'"
            ")",
            name="event_type",
        ),
        sa.CheckConstraint(
            "outcome IN ('SUCCEEDED', 'DENIED', 'FAILED', 'SUSPICIOUS')",
            name="outcome",
        ),
        sa.CheckConstraint("severity IN ('INFO', 'WARNING', 'CRITICAL')", name="severity"),
        sa.CheckConstraint(
            "actor_kind IS NULL OR actor_kind IN ("
            "'PATRON_ADMIN', 'PATRON_DELEGATE', 'COLLABORATEUR', "
            "'PARTENAIRE_EXTERNAL', 'SUPPORT_BREAK_GLASS', 'SYSTEM'"
            ")",
            name="actor_kind",
        ),
        sa.CheckConstraint(
            "auth_strength IS NULL OR auth_strength IN ('PASSWORD', 'MFA', 'MFA_STEP_UP')",
            name="auth_strength",
        ),
        sa.CheckConstraint(
            "source_ip_hash IS NULL OR source_ip_hash ~ '^[a-f0-9]{64}$'",
            name="source_ip_hash",
        ),
        sa.CheckConstraint("jsonb_typeof(metadata_json) = 'object'", name="metadata_object"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_security_audit__tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_security_audit_events"),
    )
    op.create_index(
        "ix_security_audit__tenant_occurred",
        "security_audit_events",
        ["tenant_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_security_audit__event_occurred",
        "security_audit_events",
        ["event_type", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_security_audit__correlation",
        "security_audit_events",
        ["correlation_id"],
        unique=False,
    )
    op.execute(
        """
        CREATE FUNCTION protect_security_audit_append_only() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'SECURITY_AUDIT_APPEND_ONLY';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_security_audit_append_only
        BEFORE UPDATE OR DELETE ON security_audit_events
        FOR EACH ROW EXECUTE FUNCTION protect_security_audit_append_only();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_security_audit_append_only ON security_audit_events"
    )
    op.execute("DROP FUNCTION IF EXISTS protect_security_audit_append_only()")
    op.drop_index("ix_security_audit__correlation", table_name="security_audit_events")
    op.drop_index("ix_security_audit__event_occurred", table_name="security_audit_events")
    op.drop_index("ix_security_audit__tenant_occurred", table_name="security_audit_events")
    op.drop_table("security_audit_events")
