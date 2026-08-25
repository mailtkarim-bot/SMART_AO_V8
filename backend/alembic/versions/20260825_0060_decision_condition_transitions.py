"""Decision condition transitions.

Revision ID: 20260825_0060
Revises: 20260824_0059
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260825_0060"
down_revision = "20260824_0059"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ux_decisions__tenant_active_key",
        "decisions",
        ["tenant_id", "decision_key_hash"],
        unique=True,
        postgresql_where=sa.text(
            "validity = 'CURRENT' AND lifecycle NOT IN ('SUPERSEDED', 'CANCELLED')"
        ),
    )
    op.create_table(
        "decision_condition_transitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("condition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", sa.String(length=24), nullable=False),
        sa.Column("to_status", sa.String(length=24), nullable=False),
        sa.Column("satisfied_evidence_ref_json", postgresql.JSONB(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("aggregate_revision", sa.Integer(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_decision_condition_transitions"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "decision_id"],
            ["decisions.tenant_id", "decisions.id"],
            name="fk_decision_condition_transitions__decision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "condition_id"],
            ["decision_conditions.tenant_id", "decision_conditions.id"],
            name="fk_decision_condition_transitions__condition",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_decision_condition_transitions__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "command_id", name="uq_decision_condition_transitions__command"
        ),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_decision_condition_transitions__idempotency"
        ),
        sa.CheckConstraint(
            "from_status = 'OPEN' AND to_status IN ('SATISFIED', 'FAILED')",
            name="valid_transition",
        ),
        sa.CheckConstraint("aggregate_revision > 0", name="positive_revision"),
        sa.CheckConstraint(
            "to_status <> 'SATISFIED' OR satisfied_evidence_ref_json IS NOT NULL",
            name="satisfied_requires_evidence",
        ),
        sa.CheckConstraint(
            "to_status <> 'FAILED' OR NULLIF(BTRIM(failure_reason), '') IS NOT NULL",
            name="failed_requires_reason",
        ),
    )
    op.create_index(
        "ix_decision_condition_transitions__tenant_decision",
        "decision_condition_transitions",
        ["tenant_id", "decision_id", "aggregate_revision"],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_decision_condition_transition_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'DECISION_CONDITION_TRANSITION_APPEND_ONLY';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_decision_condition_transitions_append_only
        BEFORE UPDATE OR DELETE ON decision_condition_transitions
        FOR EACH ROW EXECUTE FUNCTION prevent_decision_condition_transition_mutation();
        """
    )


def downgrade() -> None:
    op.drop_index("ux_decisions__tenant_active_key", table_name="decisions")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_decision_condition_transitions_append_only "
        "ON decision_condition_transitions"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_decision_condition_transition_mutation()")
    op.drop_index(
        "ix_decision_condition_transitions__tenant_decision",
        table_name="decision_condition_transitions",
    )
    op.drop_table("decision_condition_transitions")
