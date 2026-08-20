"""Create append-only patron action transitions.

Revision ID: 20260818_0041
Revises: 20260818_0040
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260818_0041"
down_revision = "20260818_0040"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "patron_action_transitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_state", sa.String(length=16), nullable=False),
        sa.Column("to_state", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("aggregate_revision", sa.Integer, nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_patron_action_transitions"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "action_id"],
            ["patron_actions.tenant_id", "patron_actions.id"],
            name="fk_patron_action_transitions__action",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_patron_action_transitions__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "action_id",
            "aggregate_revision",
            name="uq_patron_action_transitions__revision",
        ),
        sa.UniqueConstraint(
            "tenant_id", "command_id", name="uq_patron_action_transitions__command"
        ),
        sa.CheckConstraint("aggregate_revision > 1", name="aggregate_revision_positive"),
        sa.CheckConstraint("from_state IN ('OPEN', 'IN_PROGRESS', 'WAITING')", name="from_state"),
        sa.CheckConstraint(
            "to_state IN ('IN_PROGRESS', 'WAITING', 'COMPLETED', 'ABANDONED')", name="to_state"
        ),
    )
    op.create_index(
        "ix_patron_action_transitions_tenant_id", "patron_action_transitions", ["tenant_id"]
    )
    op.create_index(
        "ix_patron_action_transitions__tenant_action_revision",
        "patron_action_transitions",
        ["tenant_id", "action_id", "aggregate_revision"],
    )
    op.execute("""
        CREATE FUNCTION prevent_patron_action_transition_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'patron action transitions are append-only';
        END;
        $$;
        CREATE TRIGGER patron_action_transitions_append_only
        BEFORE UPDATE OR DELETE ON patron_action_transitions
        FOR EACH ROW EXECUTE FUNCTION prevent_patron_action_transition_mutation();
    """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS patron_action_transitions_append_only ON patron_action_transitions"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_patron_action_transition_mutation()")
    op.drop_index(
        "ix_patron_action_transitions__tenant_action_revision",
        table_name="patron_action_transitions",
    )
    op.drop_index("ix_patron_action_transitions_tenant_id", table_name="patron_action_transitions")
    op.drop_table("patron_action_transitions")
