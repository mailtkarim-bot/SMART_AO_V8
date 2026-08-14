"""Create the immutable Case-scoped DCE impact register."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260814_0019"
down_revision = "20260814_0018"
branch_labels = None
depends_on = None

_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "case_dce_impact_runs",
        sa.Column("id", _UUID, nullable=False),
        sa.Column("tenant_id", _UUID, nullable=False),
        sa.Column("case_id", _UUID, nullable=False),
        sa.Column("predecessor_dce_version_id", _UUID, nullable=False),
        sa.Column("successor_dce_version_id", _UUID, nullable=False),
        sa.Column("input_manifest_sha256", sa.CHAR(64), nullable=False),
        sa.Column("algorithm_id", sa.String(100), nullable=False),
        sa.Column("algorithm_version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("previous_requirement_count", sa.Integer(), nullable=False),
        sa.Column("successor_requirement_count", sa.Integer(), nullable=False),
        sa.Column("failure_code", sa.String(120), nullable=True),
        sa.Column("created_by_actor_id", _UUID, nullable=False),
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
        sa.CheckConstraint("status IN ('COMPLETED', 'NO_SIGNAL')", name="status"),
        sa.CheckConstraint("previous_requirement_count >= 0", name="previous_count_nonnegative"),
        sa.CheckConstraint("successor_requirement_count >= 0", name="successor_count_nonnegative"),
        sa.CheckConstraint("failure_code IS NULL", name="failure_code_empty"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_case_dce_impact_runs__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_case_dce_impact_runs__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "predecessor_dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_case_dce_impact_runs__predecessor",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "successor_dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_case_dce_impact_runs__successor",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_case_dce_impact_runs"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_case_dce_impact_runs__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "case_id",
            "predecessor_dce_version_id",
            "successor_dce_version_id",
            "input_manifest_sha256",
            "algorithm_id",
            "algorithm_version",
            name="uq_case_dce_impact_runs__identity",
        ),
    )
    op.create_index(
        "ix_case_dce_impact_runs__tenant_case_created",
        "case_dce_impact_runs",
        ["tenant_id", "case_id", "created_at"],
    )
    op.create_index(
        "ix_case_dce_impact_runs_tenant_id", "case_dce_impact_runs", ["tenant_id"]
    )

    op.create_table(
        "case_dce_impact_items",
        sa.Column("id", _UUID, nullable=False),
        sa.Column("tenant_id", _UUID, nullable=False),
        sa.Column("impact_run_id", _UUID, nullable=False),
        sa.Column("case_id", _UUID, nullable=False),
        sa.Column("impact_kind", sa.String(64), nullable=False),
        sa.Column("previous_requirement_id", _UUID, nullable=True),
        sa.Column("successor_requirement_id", _UUID, nullable=True),
        sa.Column("review_state", sa.String(32), nullable=False),
        sa.Column("evidence_code", sa.String(64), nullable=False),
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
            "impact_kind IN ('DCE_VERSION_REPLACED', 'PREVIOUS_REQUIREMENT_REQUIRES_REVIEW', "
            "'SUCCESSOR_REQUIREMENT_CANDIDATE', 'VERSION_HAS_NO_MATERIALIZED_SIGNAL')",
            name="impact_kind",
        ),
        sa.CheckConstraint(
            "review_state IN ('REVIEW_REQUIRED', 'PENDING_HUMAN_REVIEW')", name="review_state"
        ),
        sa.CheckConstraint(
            "evidence_code IN ('RECTIFICATION_CHAIN', 'PREVIOUS_REQUIREMENT', "
            "'SUCCESSOR_REQUIREMENT', 'NO_SIGNAL')",
            name="evidence_code",
        ),
        sa.CheckConstraint(
            "(impact_kind = 'PREVIOUS_REQUIREMENT_REQUIRES_REVIEW' "
            "AND previous_requirement_id IS NOT NULL AND successor_requirement_id IS NULL) OR "
            "(impact_kind = 'SUCCESSOR_REQUIREMENT_CANDIDATE' "
            "AND previous_requirement_id IS NULL AND successor_requirement_id IS NOT NULL) OR "
            "(impact_kind IN ('DCE_VERSION_REPLACED', 'VERSION_HAS_NO_MATERIALIZED_SIGNAL') "
            "AND previous_requirement_id IS NULL AND successor_requirement_id IS NULL)",
            name="requirement_reference_shape",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_case_dce_impact_items__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "impact_run_id"],
            ["case_dce_impact_runs.tenant_id", "case_dce_impact_runs.id"],
            name="fk_case_dce_impact_items__run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_case_dce_impact_items__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "previous_requirement_id"],
            ["dce_requirements.tenant_id", "dce_requirements.id"],
            name="fk_case_dce_impact_items__previous_requirement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "successor_requirement_id"],
            ["dce_requirements.tenant_id", "dce_requirements.id"],
            name="fk_case_dce_impact_items__successor_requirement",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_case_dce_impact_items"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_case_dce_impact_items__tenant_id"),
    )
    op.create_index(
        "ix_case_dce_impact_items__tenant_run",
        "case_dce_impact_items",
        ["tenant_id", "impact_run_id"],
    )
    op.create_index(
        "ix_case_dce_impact_items__tenant_case",
        "case_dce_impact_items",
        ["tenant_id", "case_id"],
    )
    op.create_index(
        "ix_case_dce_impact_items_tenant_id", "case_dce_impact_items", ["tenant_id"]
    )

    op.execute(
        "CREATE FUNCTION prevent_case_dce_impact_mutation() RETURNS trigger AS $$ "
        "BEGIN RAISE EXCEPTION 'CASE_DCE_IMPACT_APPEND_ONLY'; END; $$ LANGUAGE plpgsql;"
    )
    for table in ("case_dce_impact_runs", "case_dce_impact_items"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION prevent_case_dce_impact_mutation()"
        )


def downgrade() -> None:
    for table in ("case_dce_impact_items", "case_dce_impact_runs"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    op.execute("DROP FUNCTION IF EXISTS prevent_case_dce_impact_mutation()")
    op.execute("DROP INDEX IF EXISTS ix_case_dce_impact_items_tenant_id")
    op.drop_index("ix_case_dce_impact_items__tenant_case", table_name="case_dce_impact_items")
    op.drop_index("ix_case_dce_impact_items__tenant_run", table_name="case_dce_impact_items")
    op.drop_table("case_dce_impact_items")
    op.execute("DROP INDEX IF EXISTS ix_case_dce_impact_runs_tenant_id")
    op.drop_index("ix_case_dce_impact_runs__tenant_case_created", table_name="case_dce_impact_runs")
    op.drop_table("case_dce_impact_runs")
