"""Create collaborator work task roots and append-only results.

Revision ID: 20260817_0030
Revises: 20260817_0029
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260817_0030"
down_revision = "20260817_0029"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collaborator_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requirement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_kind", sa.String(48), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("objective", sa.String(2_000), nullable=False),
        sa.Column("priority", sa.String(16), server_default="NORMAL", nullable=False),
        sa.Column("state", sa.String(16), server_default="READY", nullable=False),
        sa.Column("functional_key", sa.String(500), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("aggregate_revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_collab_tasks__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_collab_tasks__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["case_assignments.tenant_id", "case_assignments.id"],
            name="fk_collab_tasks__assignment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "requirement_id"],
            ["dce_requirements.tenant_id", "dce_requirements.id"],
            name="fk_collab_tasks__requirement",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_collaborator_tasks"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_collab_tasks__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "assignment_id", "functional_key", name="uq_collab_task__functional"
        ),
        sa.CheckConstraint(
            "state IN ('READY', 'IN_PROGRESS', 'BLOCKED', 'COMPLETED', 'ABANDONED')", name="state"
        ),
        sa.CheckConstraint("aggregate_revision >= 0", name="aggregate_revision"),
        sa.CheckConstraint("priority IN ('LOW', 'NORMAL', 'HIGH', 'CRITICAL')", name="priority"),
    )
    op.create_index(        "ix_collaborator_tasks_tenant_id", "collaborator_tasks", ["tenant_id"]
)
    op.create_index(
        "ix_collab_tasks__tenant_assignment_state",
        "collaborator_tasks",
        ["tenant_id", "assignment_id", "state", "created_at"],
    )
    op.create_index(
        "ix_collab_tasks__tenant_case_state",
        "collaborator_tasks",
        ["tenant_id", "case_id", "state", "created_at"],
    )

    op.create_table(
        "collaborator_task_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_revision", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("result_text", sa.String(8_000), nullable=False),
        sa.Column("source_locator", sa.String(500), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_collab_task_results__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["collaborator_tasks.tenant_id", "collaborator_tasks.id"],
            name="fk_collab_task_results__task",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_collab_task_results__membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_collaborator_task_results"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_collab_task_results__tenant_id"),
        sa.CheckConstraint(
            "outcome IN ('RECORDED', 'NOT_APPLICABLE', 'UNABLE_TO_COMPLETE')", name="outcome"
        ),
        sa.CheckConstraint("task_revision >= 0", name="task_revision"),
        sa.CheckConstraint("length(trim(result_text)) > 0", name="result_text_nonempty"),
    )
    op.create_index(
        "ix_collaborator_task_results_tenant_id",
        "collaborator_task_results",
        ["tenant_id"],
    )
    op.create_index(
        "ix_collab_task_results__tenant_task_revision",
        "collaborator_task_results",
        ["tenant_id", "task_id", "task_revision"],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_collaborator_task_result_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'collaborator task results are append-only'; END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER collaborator_task_results_append_only
        BEFORE UPDATE OR DELETE ON collaborator_task_results
        FOR EACH ROW EXECUTE FUNCTION prevent_collaborator_task_result_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS collaborator_task_results_append_only ON collaborator_task_results"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_collaborator_task_result_mutation()")
    op.drop_index(
        "ix_collab_task_results__tenant_task_revision", table_name="collaborator_task_results"
    )
    op.execute("DROP INDEX IF EXISTS ix_collaborator_task_results_tenant_id")
    op.drop_table("collaborator_task_results")
    op.drop_index("ix_collab_tasks__tenant_case_state", table_name="collaborator_tasks")
    op.drop_index("ix_collab_tasks__tenant_assignment_state", table_name="collaborator_tasks")
    op.execute("DROP INDEX IF EXISTS ix_collaborator_tasks_tenant_id")
    op.execute("DROP INDEX IF EXISTS ix_collab_tasks_tenant_id")
    op.drop_table("collaborator_tasks")
