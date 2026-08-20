"""Create the first patron action queue projection.

Revision ID: 20260818_0038
Revises: 20260818_0037
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260818_0038"
down_revision = "20260818_0037"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _append_only(table: str, function: str, trigger: str, message: str) -> None:
    op.execute(
        f"""
        CREATE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '{message}';
        END;
        $$;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {trigger}
        BEFORE UPDATE OR DELETE ON {table}
        FOR EACH ROW EXECUTE FUNCTION {function}();
        """
    )


def _drop_append_only(table: str, function: str, trigger: str) -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
    op.execute(f"DROP FUNCTION IF EXISTS {function}()")


def upgrade() -> None:
    op.create_table(
        "patron_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("functional_key", sa.String(length=240), nullable=False),
        sa.Column("action_type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("why_now", sa.String(length=1000), nullable=False),
        sa.Column("impact", sa.String(length=1000), nullable=False),
        sa.Column("recommended_action", sa.String(length=1000), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_refs_json", postgresql.JSONB, nullable=False),
        sa.Column("aggregate_revision", sa.Integer, server_default="1", nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_patron_actions"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_patron_actions__tenant", ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_patron_actions__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "functional_key", name="uq_patron_actions__functional_key"
        ),
        sa.CheckConstraint("aggregate_revision > 0", name="aggregate_revision_positive"),
        sa.CheckConstraint(
            "state IN ('OPEN', 'IN_PROGRESS', 'WAITING', 'COMPLETED', 'ABANDONED')", name="state"
        ),
        sa.CheckConstraint(
            "severity IN ('URGENT', 'BLOCKING', 'AT_RISK', 'MONITOR')", name="severity"
        ),
        sa.CheckConstraint(
            "action_type IN ("
            "'REVIEW_PREPARATION', 'CONTROL_SUBMISSION', 'VALIDATE_PRICE', 'DECIDE_GO_NO_GO'"
            ")",
            name="action_type",
        ),
    )
    op.create_index("ix_patron_actions_tenant_id", "patron_actions", ["tenant_id"])
    op.create_index(
        "ix_patron_actions__tenant_state_due",
        "patron_actions",
        ["tenant_id", "state", "severity", "due_at"],
    )
    _append_only(
        "patron_actions",
        "prevent_patron_action_mutation",
        "patron_actions_append_only",
        "patron actions are append-only",
    )


def downgrade() -> None:
    _drop_append_only(
        "patron_actions",
        "prevent_patron_action_mutation",
        "patron_actions_append_only",
    )
    op.drop_index("ix_patron_actions__tenant_state_due", table_name="patron_actions")
    op.drop_index("ix_patron_actions_tenant_id", table_name="patron_actions")
    op.drop_table("patron_actions")
