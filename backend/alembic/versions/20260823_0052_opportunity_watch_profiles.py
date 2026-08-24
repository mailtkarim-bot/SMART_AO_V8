"""Create patron opportunity watch profiles and immutable versions."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260823_0052"
down_revision = "20260823_0051"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "opportunity_watch_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("aggregate_revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=32), server_default="ACTIVE", nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_opportunity_watch_profiles__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_opportunity_watch_profiles"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_opportunity_watch_profiles__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "command_id", name="uq_opportunity_watch_profiles__tenant_command"
        ),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_opportunity_watch_profiles__tenant_idempotency"
        ),
        sa.CheckConstraint(
            "state IN ('ACTIVE', 'PAUSED')", name="state_allowed"
        ),
        sa.CheckConstraint("aggregate_revision >= 0", name="aggregate_revision_non_negative"),
        sa.CheckConstraint("current_version >= 1", name="current_version_positive"),
        sa.CheckConstraint("length(trim(name)) > 0", name="name_non_empty"),
    )
    op.create_index(
        "ix_opportunity_watch_profiles__tenant_state_created",
        "opportunity_watch_profiles",
        ["tenant_id", "state", "created_at"],
    )

    op.create_table(
        "opportunity_watch_profile_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("criteria_json", postgresql.JSONB(), nullable=False),
        sa.Column("criteria_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_opportunity_watch_profile_versions__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "profile_id"],
            ["opportunity_watch_profiles.tenant_id", "opportunity_watch_profiles.id"],
            name="fk_opportunity_watch_profile_versions__profiles__tenant_profile",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_opportunity_watch_profile_versions"),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uq_opportunity_watch_profile_versions__tenant_id"
        ),
        sa.UniqueConstraint(
            "tenant_id", "profile_id", "version_number",
            name="uq_opportunity_watch_profile_versions__profile_version",
        ),
        sa.UniqueConstraint(
            "tenant_id", "command_id", name="uq_opportunity_watch_profile_versions__tenant_command"
        ),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key",
            name="uq_opportunity_watch_profile_versions__tenant_idempotency",
        ),
        sa.CheckConstraint("version_number >= 1", name="version_number_positive"),
        sa.CheckConstraint("jsonb_typeof(criteria_json) = 'object'", name="criteria_object"),
        sa.CheckConstraint(
            "criteria_sha256 ~ '^[a-f0-9]{64}$'", name="criteria_sha256_hex"
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name="name_non_empty"),
    )
    op.create_index(
        "ix_opportunity_watch_profile_versions__tenant_profile_version",
        "opportunity_watch_profile_versions",
        ["tenant_id", "profile_id", "version_number"],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_opportunity_watch_profile_version_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'opportunity watch profile versions are append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER opportunity_watch_profile_versions_append_only
        BEFORE UPDATE OR DELETE ON opportunity_watch_profile_versions
        FOR EACH ROW EXECUTE FUNCTION prevent_opportunity_watch_profile_version_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS opportunity_watch_profile_versions_append_only "
        "ON opportunity_watch_profile_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_opportunity_watch_profile_version_mutation()")
    op.drop_index(
        "ix_opportunity_watch_profile_versions__tenant_profile_version",
        table_name="opportunity_watch_profile_versions",
    )
    op.drop_table("opportunity_watch_profile_versions")
    op.drop_index(
        "ix_opportunity_watch_profiles__tenant_state_created",
        table_name="opportunity_watch_profiles",
    )
    op.drop_table("opportunity_watch_profiles")
