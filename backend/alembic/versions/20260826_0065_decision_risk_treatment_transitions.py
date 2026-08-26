"""Create append-only structured risk treatment transitions.

Revision ID: 20260826_0065
Revises: 20260826_0064
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260826_0065"
down_revision = "20260826_0064"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decision_risk_treatment_transitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("risk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_treatment", sa.String(length=16), nullable=False),
        sa.Column("to_treatment", sa.String(length=16), nullable=False),
        sa.Column("evidence_excerpt", sa.String(length=2000), nullable=False),
        sa.Column("evidence_locator_json", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_start_byte_offset", sa.Integer(), nullable=False),
        sa.Column("evidence_end_byte_offset", sa.Integer(), nullable=False),
        sa.Column("rationale", sa.String(length=2000), nullable=False),
        sa.Column("aggregate_revision", sa.Integer(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_decision_risk_transitions__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "risk_id"],
            ["decision_risks.tenant_id", "decision_risks.id"],
            name="fk_decision_risk_transitions__risk",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_decision_risk_treatment_transitions"),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uq_decision_risk_transitions__tenant_id"
        ),
        sa.UniqueConstraint(
            "tenant_id", "command_id", name="uq_decision_risk_transitions__command"
        ),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_decision_risk_transitions__idempotency"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "risk_id",
            "aggregate_revision",
            name="uq_decision_risk_transitions__revision",
        ),
        sa.CheckConstraint(
            "(from_treatment = 'OPEN' AND to_treatment IN ('ACCEPTED', 'MITIGATED')) OR "
            "(from_treatment = 'ACCEPTED' AND to_treatment = 'MITIGATED')",
            name="valid_transition",
        ),
        sa.CheckConstraint("aggregate_revision > 1", name="positive_transition_revision"),
        sa.CheckConstraint("char_length(btrim(evidence_excerpt)) > 0", name="evidence_nonempty"),
        sa.CheckConstraint("char_length(btrim(rationale)) > 0", name="rationale_nonempty"),
        sa.CheckConstraint(
            "evidence_start_byte_offset >= 0 AND "
            "evidence_end_byte_offset > evidence_start_byte_offset",
            name="evidence_offsets_ordered",
        ),
    )
    op.create_index(
        "ix_decision_risk_transitions__tenant_risk_revision",
        "decision_risk_treatment_transitions",
        ["tenant_id", "risk_id", "aggregate_revision"],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_decision_risk_treatment_transition_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'DECISION_RISK_TREATMENT_TRANSITION_APPEND_ONLY';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_decision_risk_treatment_transitions_append_only
        BEFORE UPDATE OR DELETE ON decision_risk_treatment_transitions
        FOR EACH ROW EXECUTE FUNCTION prevent_decision_risk_treatment_transition_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_decision_risk_treatment_transitions_append_only "
        "ON decision_risk_treatment_transitions"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_decision_risk_treatment_transition_mutation()")
    op.drop_index(
        "ix_decision_risk_transitions__tenant_risk_revision",
        table_name="decision_risk_treatment_transitions",
    )
    op.drop_table("decision_risk_treatment_transitions")
