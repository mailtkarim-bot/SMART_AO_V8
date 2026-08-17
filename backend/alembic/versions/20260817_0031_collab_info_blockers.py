"""Create collaborator information requests, responses and task blockers.

Revision ID: 20260817_0031
Revises: 20260817_0030
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260817_0031"
down_revision = "20260817_0030"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _uuid(name: str) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=False)


def upgrade() -> None:
    op.create_table(
        "collaborator_information_requests",
        _uuid("id"),
        _uuid("tenant_id"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        _uuid("task_id"),
        sa.Column("request_kind", sa.String(32), nullable=False),
        sa.Column("subject", sa.String(240), nullable=False),
        sa.Column("question", sa.String(4_000), nullable=False),
        sa.Column("requested_object", sa.String(1_000), nullable=False),
        sa.Column("reason", sa.String(2_000), nullable=False),
        sa.Column("priority", sa.String(16), server_default="NORMAL", nullable=False),
        sa.Column("state", sa.String(16), server_default="OPEN", nullable=False),
        sa.Column("functional_key", sa.String(700), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("aggregate_revision", sa.Integer(), server_default="0", nullable=False),
        _uuid("actor_id"),
        _uuid("membership_id"),
        _uuid("command_id"),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_collab_info_requests__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["collaborator_tasks.tenant_id", "collaborator_tasks.id"],
            name="fk_collab_info_requests__task",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_collaborator_information_requests"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_collab_info_requests__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "task_id", "functional_key", name="uq_collab_info_request__functional"
        ),
        sa.CheckConstraint(
            "request_kind IN ("
            "'MISSING_SOURCE', 'CLARIFICATION', 'OWNER_CONFIRMATION', "
            "'DEADLINE_CONFIRMATION')",
            name="request_kind",
        ),
        sa.CheckConstraint("priority IN ('LOW', 'NORMAL', 'HIGH', 'CRITICAL')", name="priority"),
        sa.CheckConstraint("state IN ('OPEN', 'ANSWERED', 'CLOSED', 'CANCELLED')", name="state"),
        sa.CheckConstraint("aggregate_revision >= 0", name="aggregate_revision"),
    )
    op.create_index(
        "ix_collaborator_information_requests_tenant_id",
        "collaborator_information_requests",
        ["tenant_id"],
    )
    op.create_index(
        "ix_collab_info_requests__tenant_task_state",
        "collaborator_information_requests",
        ["tenant_id", "task_id", "state", "created_at"],
    )

    op.create_table(
        "collaborator_information_responses",
        _uuid("id"),
        _uuid("tenant_id"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        _uuid("request_id"),
        sa.Column("request_revision", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("response_text", sa.String(8_000), nullable=False),
        sa.Column("source_locator", sa.String(500), nullable=True),
        _uuid("actor_id"),
        _uuid("membership_id"),
        _uuid("command_id"),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_collab_info_responses__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "request_id"],
            ["collaborator_information_requests.tenant_id", "collaborator_information_requests.id"],
            name="fk_collab_info_responses__request",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_collaborator_information_responses"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_collab_info_responses__tenant_id"),
        sa.CheckConstraint(
            "outcome IN ('ANSWERED', 'NOT_AVAILABLE', 'NEEDS_CLARIFICATION')", name="outcome"
        ),
        sa.CheckConstraint("request_revision >= 0", name="request_revision"),
        sa.CheckConstraint("length(trim(response_text)) > 0", name="response_text_nonempty"),
    )
    op.create_index(
        "ix_collaborator_information_responses_tenant_id",
        "collaborator_information_responses",
        ["tenant_id"],
    )
    op.create_index(
        "ix_collab_info_responses__tenant_request_revision",
        "collaborator_information_responses",
        ["tenant_id", "request_id", "request_revision"],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_collaborator_information_response_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'collaborator information responses are append-only'; END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER collaborator_information_responses_append_only
        BEFORE UPDATE OR DELETE ON collaborator_information_responses
        FOR EACH ROW EXECUTE FUNCTION prevent_collaborator_information_response_mutation();
        """
    )

    op.create_table(
        "collaborator_task_blockers",
        _uuid("id"),
        _uuid("tenant_id"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        _uuid("task_id"),
        sa.Column("task_revision", sa.Integer(), nullable=False),
        sa.Column("blocker_kind", sa.String(32), nullable=False),
        sa.Column("description", sa.String(4_000), nullable=False),
        sa.Column("source_locator", sa.String(500), nullable=True),
        sa.Column("resolution_owner", sa.String(24), nullable=False),
        sa.Column("state", sa.String(16), server_default="OPEN", nullable=False),
        sa.Column("resolution_note", sa.String(4_000), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        _uuid("actor_id"),
        _uuid("membership_id"),
        _uuid("command_id"),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_collab_task_blockers__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["collaborator_tasks.tenant_id", "collaborator_tasks.id"],
            name="fk_collab_task_blockers__task",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_collaborator_task_blockers"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_collab_task_blockers__tenant_id"),
        sa.CheckConstraint(
            "blocker_kind IN ("
            "'MISSING_INFORMATION', 'EXTERNAL_DEPENDENCY', "
            "'SOURCE_CONFLICT', 'REVIEW_REQUIRED')",
            name="blocker_kind",
        ),
        sa.CheckConstraint(
            "resolution_owner IN ('COLLABORATEUR', 'PATRON_ADMIN', 'EXTERNAL_PARTY')",
            name="resolution_owner",
        ),
        sa.CheckConstraint("state IN ('OPEN', 'RESOLVED')", name="state"),
        sa.CheckConstraint(
            "state <> 'RESOLVED' OR (resolution_note IS NOT NULL AND resolved_at IS NOT NULL)",
            name="resolution_fields",
        ),
    )
    op.create_index(
        "ix_collaborator_task_blockers_tenant_id", "collaborator_task_blockers", ["tenant_id"]
    )
    op.create_index(
        "ix_collab_task_blockers__tenant_task_state",
        "collaborator_task_blockers",
        ["tenant_id", "task_id", "state", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_collab_task_blockers__tenant_task_state", table_name="collaborator_task_blockers"
    )
    op.execute("DROP INDEX IF EXISTS ix_collaborator_task_blockers_tenant_id")
    op.drop_table("collaborator_task_blockers")
    op.execute(
        "DROP TRIGGER IF EXISTS collaborator_information_responses_append_only "
        "ON collaborator_information_responses"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_collaborator_information_response_mutation()")
    op.drop_index(
        "ix_collab_info_responses__tenant_request_revision",
        table_name="collaborator_information_responses",
    )
    op.execute("DROP INDEX IF EXISTS ix_collaborator_information_responses_tenant_id")
    op.drop_table("collaborator_information_responses")
    op.drop_index(
        "ix_collab_info_requests__tenant_task_state", table_name="collaborator_information_requests"
    )
    op.execute("DROP INDEX IF EXISTS ix_collaborator_information_requests_tenant_id")
    op.drop_table("collaborator_information_requests")
