"""Create immutable deterministic DCE requirement materialization registry.

Revision ID: 20260814_0016
Revises: 20260814_0015
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260814_0016"
down_revision = "20260814_0015"
branch_labels = None
depends_on = None

_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "dce_requirement_materialization_runs",
        sa.Column("id", _UUID, nullable=False),
        sa.Column("tenant_id", _UUID, nullable=False),
        sa.Column("dce_version_id", _UUID, nullable=False),
        sa.Column("dce_rc_analysis_id", _UUID, nullable=False),
        sa.Column("input_manifest_sha256", sa.CHAR(64), nullable=False),
        sa.Column("materializer_id", sa.String(100), nullable=False),
        sa.Column("materializer_version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("source_observation_count", sa.Integer(), nullable=False),
        sa.Column("failure_code", sa.String(120), nullable=True),
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
            "status IN ('COMPLETED', 'NO_SIGNAL', 'REJECTED_LIMIT', 'FAILED_SAFE')", name="status"
        ),
        sa.CheckConstraint("source_observation_count >= 0", name="source_obs_nonneg"),
        sa.CheckConstraint(
            "(status IN ('COMPLETED', 'NO_SIGNAL') AND failure_code IS NULL) OR "
            "(status NOT IN ('COMPLETED', 'NO_SIGNAL') AND failure_code IS NOT NULL)",
            name="status_failure_code",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_dce_req_runs__tenants", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_req_runs__version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_rc_analysis_id"],
            ["dce_rc_analysis_runs.tenant_id", "dce_rc_analysis_runs.id"],
            name="fk_dce_req_runs__analysis",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dce_requirement_materialization_runs"),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uq_dce_requirement_materialization_runs__tenant_id"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "dce_version_id",
            "dce_rc_analysis_id",
            "input_manifest_sha256",
            "materializer_id",
            "materializer_version",
            name="uq_dce_req_run_identity",
        ),
    )
    op.create_index(
        "ix_dce_req_runs__tenant_version_created",
        "dce_requirement_materialization_runs",
        ["tenant_id", "dce_version_id", "created_at"],
    )
    op.create_index(
        "ix_dce_requirement_materialization_runs_tenant_id",
        "dce_requirement_materialization_runs",
        ["tenant_id"],
    )
    op.create_table(
        "dce_requirements",
        sa.Column("id", _UUID, nullable=False),
        sa.Column("tenant_id", _UUID, nullable=False),
        sa.Column("requirements_run_id", _UUID, nullable=False),
        sa.Column("dce_version_id", _UUID, nullable=False),
        sa.Column("source_observation_id", _UUID, nullable=False),
        sa.Column("requirement_type", sa.String(64), nullable=False),
        sa.Column("directive_signal", sa.String(32), nullable=False),
        sa.Column("confirmation_status", sa.String(32), nullable=False),
        sa.Column("uncertainty_status", sa.String(32), nullable=False),
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
            "requirement_type IN ('CANDIDATURE_DOCUMENT', 'OFFER_DOCUMENT', "
            "'SUBMISSION_DEADLINE_SIGNAL', 'SUBMISSION_CHANNEL', "
            "'FILE_CONSTRAINT', 'SITE_VISIT', 'AWARD_CRITERION_SIGNAL', "
            "'NEGOTIATION_SIGNAL', 'OFFER_VALIDITY_SIGNAL')",
            name="requirement_type",
        ),
        sa.CheckConstraint(
            "directive_signal IN ('REQUIRED_SIGNAL', 'OPTIONAL_SIGNAL', 'UNSPECIFIED')",
            name="directive",
        ),
        sa.CheckConstraint(
            "confirmation_status = 'PENDING_HUMAN_CONFIRMATION'", name="confirmation"
        ),
        sa.CheckConstraint("uncertainty_status = 'SOURCE_SIGNAL_ONLY'", name="uncertainty"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_dce_requirements__tenants", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "requirements_run_id"],
            [
                "dce_requirement_materialization_runs.tenant_id",
                "dce_requirement_materialization_runs.id",
            ],
            name="fk_dce_requirements__run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_requirements__version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "source_observation_id"],
            ["dce_rc_requirement_observations.tenant_id", "dce_rc_requirement_observations.id"],
            name="fk_dce_requirements__observation",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dce_requirements"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_requirements__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "requirements_run_id",
            "source_observation_id",
            name="uq_dce_requirement_source_obs",
        ),
    )
    op.create_index(
        "ix_dce_requirements__tenant_run", "dce_requirements", ["tenant_id", "requirements_run_id"]
    )
    op.create_index("ix_dce_requirements_tenant_id", "dce_requirements", ["tenant_id"])
    op.create_table(
        "dce_requirement_sources",
        sa.Column("id", _UUID, nullable=False),
        sa.Column("tenant_id", _UUID, nullable=False),
        sa.Column("requirement_id", _UUID, nullable=False),
        sa.Column("source_observation_id", _UUID, nullable=False),
        sa.Column("fragment_id", _UUID, nullable=False),
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
        sa.CheckConstraint("start_byte_offset >= 0", name="start_offset_nonneg"),
        sa.CheckConstraint("end_byte_offset > start_byte_offset", name="offsets_ordered"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_dce_req_sources__tenants", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "requirement_id"],
            ["dce_requirements.tenant_id", "dce_requirements.id"],
            name="fk_dce_req_sources__requirement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "source_observation_id"],
            ["dce_rc_requirement_observations.tenant_id", "dce_rc_requirement_observations.id"],
            name="fk_dce_req_sources__observation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "fragment_id"],
            ["dce_document_extraction_fragments.tenant_id", "dce_document_extraction_fragments.id"],
            name="fk_dce_req_sources__fragment",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dce_requirement_sources"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_requirement_sources__tenant_id"),
        sa.UniqueConstraint("tenant_id", "requirement_id", name="uq_dce_req_source_requirement"),
    )
    op.create_index(
        "ix_dce_req_sources__tenant_requirement",
        "dce_requirement_sources",
        ["tenant_id", "requirement_id"],
    )
    op.create_index(
        "ix_dce_requirement_sources_tenant_id", "dce_requirement_sources", ["tenant_id"]
    )
    op.execute(
        "CREATE FUNCTION prevent_dce_requirement_mutation() RETURNS trigger AS $$ "
        "BEGIN RAISE EXCEPTION 'DCE_REQUIREMENT_APPEND_ONLY'; END; $$ LANGUAGE plpgsql;"
    )
    for table in (
        "dce_requirement_materialization_runs",
        "dce_requirements",
        "dce_requirement_sources",
    ):
        trigger_sql = (
            f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION prevent_dce_requirement_mutation()"
        )
        op.execute(trigger_sql)


def downgrade() -> None:
    for table in (
        "dce_requirement_sources",
        "dce_requirements",
        "dce_requirement_materialization_runs",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    op.execute("DROP FUNCTION IF EXISTS prevent_dce_requirement_mutation()")
    op.execute("DROP INDEX IF EXISTS ix_dce_requirement_sources_tenant_id")
    op.drop_index("ix_dce_req_sources__tenant_requirement", table_name="dce_requirement_sources")
    op.drop_table("dce_requirement_sources")
    op.execute("DROP INDEX IF EXISTS ix_dce_requirements_tenant_id")
    op.drop_index("ix_dce_requirements__tenant_run", table_name="dce_requirements")
    op.drop_table("dce_requirements")
    op.execute("DROP INDEX IF EXISTS ix_dce_requirement_materialization_runs_tenant_id")
    op.drop_index(
        "ix_dce_req_runs__tenant_version_created", table_name="dce_requirement_materialization_runs"
    )
    op.drop_table("dce_requirement_materialization_runs")
