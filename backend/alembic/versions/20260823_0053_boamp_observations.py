"""Create auditable BOAMP ingestion runs and observations."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260823_0053"
down_revision = "20260823_0052"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "boamp_ingestion_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="RECORDED", nullable=False),
        sa.Column("pages_read", sa.Integer(), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("truncated", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="boamp_ingestion_runs_tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "actor_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.identity_id"],
            name="boamp_ingestion_runs_actor",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "profile_id"],
            ["opportunity_watch_profiles.tenant_id", "opportunity_watch_profiles.id"],
            name="boamp_ingestion_runs_profile",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "profile_id", "profile_version"],
            [
                "opportunity_watch_profile_versions.tenant_id",
                "opportunity_watch_profile_versions.profile_id",
                "opportunity_watch_profile_versions.version_number",
            ],
            name="boamp_ingestion_runs_profile_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_boamp_ingestion_runs"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_boamp_ingestion_runs_tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_boamp_ingestion_runs_command"),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_boamp_ingestion_runs_idempotency"
        ),
        sa.CheckConstraint(
            "status IN ('RECORDED', 'REJECTED')", name="boamp_ingestion_runs_status"
        ),
        sa.CheckConstraint("profile_version >= 1", name="boamp_ingestion_runs_profile_version"),
        sa.CheckConstraint("pages_read >= 0", name="boamp_ingestion_runs_pages_read"),
        sa.CheckConstraint("candidate_count >= 0", name="boamp_ingestion_runs_candidate_count"),
        sa.CheckConstraint(
            "request_hash ~ '^[a-f0-9]{64}$'", name="boamp_ingestion_runs_request_hash"
        ),
    )
    op.create_index(
        "ix_boamp_ingestion_runs_tenant_created",
        "boamp_ingestion_runs",
        ["tenant_id", "created_at"],
    )

    op.create_table(
        "boamp_opportunity_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("source", sa.String(length=24), server_default="BOAMP", nullable=False),
        sa.Column("source_notice_id", sa.String(length=160), nullable=False),
        sa.Column("fingerprint_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("response_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("department_codes", postgresql.JSONB(), nullable=False),
        sa.Column("market_types", postgresql.JSONB(), nullable=False),
        sa.Column("source_status", sa.String(length=64), nullable=True),
        sa.Column("score_version", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("score_explanation_json", postgresql.JSONB(), nullable=False),
        sa.Column("score_explanation_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="boamp_observations_tenant", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_boamp_opportunity_observations"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_boamp_observations_tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "source", "source_notice_id", "fingerprint_sha256",
            name="uq_boamp_observations_source_fingerprint",
        ),
        sa.CheckConstraint("source = 'BOAMP'", name="boamp_observations_source"),
        sa.CheckConstraint(
            "fingerprint_sha256 ~ '^[a-f0-9]{64}$'", name="boamp_observations_fingerprint"
        ),
        sa.CheckConstraint("score BETWEEN 0 AND 100", name="boamp_observations_score"),
        sa.CheckConstraint(
            "score_explanation_sha256 ~ '^[a-f0-9]{64}$'",
            name="boamp_observations_score_explanation_hash",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(score_explanation_json) = 'object'",
            name="boamp_observations_score_explanation_object",
        ),
    )
    op.create_index(
        "ix_boamp_observations_tenant_source_notice",
        "boamp_opportunity_observations",
        ["tenant_id", "source", "source_notice_id"],
    )
    op.create_index(
        "ix_boamp_observations_tenant_deadline",
        "boamp_opportunity_observations",
        ["tenant_id", "response_deadline"],
    )

    op.create_table(
        "boamp_ingestion_observation_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("ingestion_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="boamp_links_tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "ingestion_run_id"],
            ["boamp_ingestion_runs.tenant_id", "boamp_ingestion_runs.id"],
            name="boamp_links_run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "observation_id"],
            ["boamp_opportunity_observations.tenant_id", "boamp_opportunity_observations.id"],
            name="boamp_links_observation",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_boamp_ingestion_observation_links"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_boamp_links_tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "ingestion_run_id", "observation_id", name="uq_boamp_links_run_observation"
        ),
    )
    op.create_index(
        "ix_boamp_links_tenant_run",
        "boamp_ingestion_observation_links",
        ["tenant_id", "ingestion_run_id"],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_boamp_observation_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'boamp ingestion runs, observations and links are append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER boamp_ingestion_runs_append_only
        BEFORE UPDATE OR DELETE ON boamp_ingestion_runs
        FOR EACH ROW EXECUTE FUNCTION prevent_boamp_observation_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER boamp_observations_append_only
        BEFORE UPDATE OR DELETE ON boamp_opportunity_observations
        FOR EACH ROW EXECUTE FUNCTION prevent_boamp_observation_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER boamp_ingestion_links_append_only
        BEFORE UPDATE OR DELETE ON boamp_ingestion_observation_links
        FOR EACH ROW EXECUTE FUNCTION prevent_boamp_observation_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS boamp_ingestion_links_append_only "
        "ON boamp_ingestion_observation_links"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS boamp_ingestion_runs_append_only "
        "ON boamp_ingestion_runs"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS boamp_observations_append_only "
        "ON boamp_opportunity_observations"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_boamp_observation_mutation()")
    op.drop_index("ix_boamp_links_tenant_run", table_name="boamp_ingestion_observation_links")
    op.drop_table("boamp_ingestion_observation_links")
    op.drop_index(
        "ix_boamp_observations_tenant_deadline", table_name="boamp_opportunity_observations"
    )
    op.drop_index(
        "ix_boamp_observations_tenant_source_notice", table_name="boamp_opportunity_observations"
    )
    op.drop_table("boamp_opportunity_observations")
    op.drop_index("ix_boamp_ingestion_runs_tenant_created", table_name="boamp_ingestion_runs")
    op.drop_table("boamp_ingestion_runs")
