"""Create immutable deterministic DCE RC analysis registry.

Revision ID: 20260814_0014
Revises: 20260813_0013
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260814_0014"
down_revision = "20260813_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dce_rc_analysis_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dce_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("input_manifest_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("analyzer_id", sa.String(length=100), nullable=False),
        sa.Column("analyzer_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_fragment_count", sa.Integer(), nullable=False),
        sa.Column("source_char_count", sa.Integer(), nullable=False),
        sa.Column("failure_code", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('COMPLETED', 'NO_RC_MARKER', 'REJECTED_LIMIT', 'FAILED_SAFE')",
            name="status",
        ),
        sa.CheckConstraint("source_fragment_count > 0", name="source_fragment_count_positive"),
        sa.CheckConstraint("source_char_count > 0", name="source_char_count_positive"),
        sa.CheckConstraint(
            "(status = 'COMPLETED' AND failure_code IS NULL) OR "
            "(status <> 'COMPLETED' AND failure_code IS NOT NULL)",
            name="status_failure_code",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_dce_rc_analysis_runs__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_rc_analysis_runs__dce_versions__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dce_rc_analysis_runs"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_rc_analysis_runs__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "dce_version_id",
            "input_manifest_sha256",
            "analyzer_id",
            "analyzer_version",
            name="uq_dce_rc_analysis_run_identity",
        ),
    )
    op.create_index(
        "ix_dce_rc_analysis__tenant_version_created",
        "dce_rc_analysis_runs",
        ["tenant_id", "dce_version_id", "created_at"],
        unique=False,
    )
    op.create_index("ix_dce_rc_analysis_runs_tenant_id", "dce_rc_analysis_runs", ["tenant_id"])

    op.create_table(
        "dce_rc_requirement_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dce_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requirement_kind", sa.String(length=64), nullable=False),
        sa.Column("directive", sa.String(length=32), nullable=False),
        sa.Column("rule_id", sa.String(length=120), nullable=False),
        sa.Column("rule_version", sa.String(length=64), nullable=False),
        sa.Column("fragment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start_byte_offset", sa.Integer(), nullable=False),
        sa.Column("end_byte_offset", sa.Integer(), nullable=False),
        sa.Column("excerpt", sa.String(length=1000), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "requirement_kind IN ("
            "'RC_DOCUMENT_CANDIDATURE', 'RC_CONTENT_OFFER', 'RC_SUBMISSION_DEADLINE', "
            "'RC_RESPONSE_CHANNEL', 'RC_FILE_CONSTRAINT', 'RC_SITE_VISIT', "
            "'RC_AWARD_CRITERION', 'RC_NEGOTIATION', 'RC_OFFER_VALIDITY'"
            ")",
            name="requirement_kind",
        ),
        sa.CheckConstraint(
            "directive IN ('REQUIRED_SIGNAL', 'OPTIONAL_SIGNAL', 'UNSPECIFIED')",
            name="directive",
        ),
        sa.CheckConstraint("char_length(excerpt) > 0", name="excerpt_nonempty"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_dce_rc_requirement_observations__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "analysis_id"],
            ["dce_rc_analysis_runs.tenant_id", "dce_rc_analysis_runs.id"],
            name="fk_dce_rc_req_obs__analysis",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_rc_req_obs__version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dce_rc_requirement_observations"),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uq_dce_rc_requirement_observations__tenant_id"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "analysis_id",
            "rule_id",
            "fragment_id",
            "start_byte_offset",
            "end_byte_offset",
            name="uq_dce_rc_req_obs_identity",
        ),
    )
    op.create_index(
        "ix_dce_rc_req_obs__tenant_analysis",
        "dce_rc_requirement_observations",
        ["tenant_id", "analysis_id"],
        unique=False,
    )
    op.create_index(
        "ix_dce_rc_requirement_observations_tenant_id",
        "dce_rc_requirement_observations",
        ["tenant_id"],
    )

    op.create_table(
        "dce_rc_requirement_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fragment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start_byte_offset", sa.Integer(), nullable=False),
        sa.Column("end_byte_offset", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("start_byte_offset >= 0", name="start_offset_nonnegative"),
        sa.CheckConstraint("end_byte_offset > start_byte_offset", name="offsets_ordered"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_dce_rc_requirement_sources__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "observation_id"],
            ["dce_rc_requirement_observations.tenant_id", "dce_rc_requirement_observations.id"],
            name="fk_dce_rc_req_source__observation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "fragment_id"],
            ["dce_document_extraction_fragments.tenant_id", "dce_document_extraction_fragments.id"],
            name="fk_dce_rc_req_source__fragment",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dce_rc_requirement_sources"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_rc_requirement_sources__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "observation_id",
            "fragment_id",
            name="uq_dce_rc_req_source_identity",
        ),
    )
    op.create_index(
        "ix_dce_rc_req_source__tenant_observation",
        "dce_rc_requirement_sources",
        ["tenant_id", "observation_id"],
        unique=False,
    )
    op.create_index(
        "ix_dce_rc_requirement_sources_tenant_id",
        "dce_rc_requirement_sources",
        ["tenant_id"],
    )

    op.execute(
        """
        CREATE FUNCTION prevent_dce_rc_analysis_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'DCE_RC_ANALYSIS_APPEND_ONLY';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table_name, trigger_name in (
        ("dce_rc_analysis_runs", "trg_dce_rc_analysis_append_only"),
        ("dce_rc_requirement_observations", "trg_dce_rc_req_obs_append_only"),
        ("dce_rc_requirement_sources", "trg_dce_rc_req_source_append_only"),
    ):
        op.execute(
            f"CREATE TRIGGER {trigger_name} BEFORE UPDATE OR DELETE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION prevent_dce_rc_analysis_mutation();"
        )

    op.execute(
        """
        CREATE FUNCTION validate_dce_rc_observation_parent()
        RETURNS trigger AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM dce_rc_analysis_runs analysis
                WHERE analysis.id = NEW.analysis_id
                  AND analysis.tenant_id = NEW.tenant_id
                  AND analysis.dce_version_id = NEW.dce_version_id
                  AND analysis.status = 'COMPLETED'
            ) THEN
                RAISE EXCEPTION 'DCE_RC_OBSERVATION_PARENT_INVALID';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_dce_rc_req_obs_parent
        BEFORE INSERT ON dce_rc_requirement_observations
        FOR EACH ROW EXECUTE FUNCTION validate_dce_rc_observation_parent();
        """
    )
    op.execute(
        """
        CREATE FUNCTION validate_dce_rc_source_parent()
        RETURNS trigger AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM dce_rc_requirement_observations observation
                JOIN dce_rc_analysis_runs analysis
                  ON analysis.id = observation.analysis_id
                 AND analysis.tenant_id = observation.tenant_id
                JOIN dce_document_extraction_fragments fragment
                  ON fragment.id = NEW.fragment_id
                 AND fragment.tenant_id = NEW.tenant_id
                JOIN dce_document_extractions extraction
                  ON extraction.id = fragment.extraction_id
                 AND extraction.tenant_id = fragment.tenant_id
                JOIN dce_documents document
                  ON document.id = extraction.dce_document_id
                 AND document.tenant_id = extraction.tenant_id
                WHERE observation.id = NEW.observation_id
                  AND observation.tenant_id = NEW.tenant_id
                  AND observation.fragment_id = NEW.fragment_id
                  AND observation.start_byte_offset = NEW.start_byte_offset
                  AND observation.end_byte_offset = NEW.end_byte_offset
                  AND analysis.status = 'COMPLETED'
                  AND document.dce_version_id = observation.dce_version_id
                  AND analysis.dce_version_id = observation.dce_version_id
            ) THEN
                RAISE EXCEPTION 'DCE_RC_SOURCE_PARENT_INVALID';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_dce_rc_req_source_parent
        BEFORE INSERT ON dce_rc_requirement_sources
        FOR EACH ROW EXECUTE FUNCTION validate_dce_rc_source_parent();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_dce_rc_req_source_parent ON dce_rc_requirement_sources")
    op.execute("DROP FUNCTION validate_dce_rc_source_parent()")
    op.execute("DROP TRIGGER trg_dce_rc_req_obs_parent ON dce_rc_requirement_observations")
    op.execute("DROP FUNCTION validate_dce_rc_observation_parent()")
    op.execute("DROP TRIGGER trg_dce_rc_req_source_append_only ON dce_rc_requirement_sources")
    op.execute("DROP TRIGGER trg_dce_rc_req_obs_append_only ON dce_rc_requirement_observations")
    op.execute("DROP TRIGGER trg_dce_rc_analysis_append_only ON dce_rc_analysis_runs")
    op.execute("DROP FUNCTION prevent_dce_rc_analysis_mutation()")
    op.drop_index("ix_dce_rc_requirement_sources_tenant_id", "dce_rc_requirement_sources")
    op.drop_index("ix_dce_rc_req_source__tenant_observation", "dce_rc_requirement_sources")
    op.drop_table("dce_rc_requirement_sources")
    op.drop_index(
        "ix_dce_rc_requirement_observations_tenant_id",
        "dce_rc_requirement_observations",
    )
    op.drop_index("ix_dce_rc_req_obs__tenant_analysis", "dce_rc_requirement_observations")
    op.drop_table("dce_rc_requirement_observations")
    op.drop_index("ix_dce_rc_analysis_runs_tenant_id", "dce_rc_analysis_runs")
    op.drop_index("ix_dce_rc_analysis__tenant_version_created", "dce_rc_analysis_runs")
    op.drop_table("dce_rc_analysis_runs")
