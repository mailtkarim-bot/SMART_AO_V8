"""Create immutable auditable OR-Tools capacity runs."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "20260823_0051"
down_revision = "20260822_0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "optimization_runs",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("solver_id", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("input_snapshot_json", JSONB, nullable=False),
        sa.Column("result_snapshot_json", JSONB, nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_optimization_runs__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_optimization_runs__cases__tenant_case",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_optimization_runs"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_optimization_runs__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "command_id", name="uq_optimization_runs__tenant_command"
        ),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_optimization_runs__tenant_idempotency"
        ),
        sa.CheckConstraint(
            "status IN ('OPTIMAL', 'FEASIBLE', 'INFEASIBLE', 'UNKNOWN', 'MODEL_INVALID')",
            name="status_allowed",
        ),
        sa.CheckConstraint("source_revision > 0", name="source_revision_positive"),
        sa.CheckConstraint(
            "jsonb_typeof(input_snapshot_json) = 'object'", name="input_snapshot_object"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(result_snapshot_json) = 'object'", name="result_snapshot_object"
        ),
        sa.CheckConstraint("input_sha256 ~ '^[a-f0-9]{64}$'", name="input_sha256_hex"),
    )
    op.create_index(
        "ix_optimization_runs__tenant_case_created",
        "optimization_runs",
        ["tenant_id", "case_id", "created_at"],
    )
    op.create_index(
        "ix_optimization_runs__tenant_case_source_revision",
        "optimization_runs",
        ["tenant_id", "case_id", "source_revision"],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_optimization_run_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'optimization runs are append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER optimization_runs_append_only
        BEFORE UPDATE OR DELETE ON optimization_runs
        FOR EACH ROW EXECUTE FUNCTION prevent_optimization_run_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS optimization_runs_append_only
        ON optimization_runs
        """
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_optimization_run_mutation()")
    op.drop_index(
        "ix_optimization_runs__tenant_case_source_revision",
        table_name="optimization_runs",
    )
    op.drop_index("ix_optimization_runs__tenant_case_created", table_name="optimization_runs")
    op.drop_table("optimization_runs")
