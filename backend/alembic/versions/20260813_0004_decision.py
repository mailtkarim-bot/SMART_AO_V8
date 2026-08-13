"""Create Decision persistence and immutable decision contexts.

Revision ID: 20260813_0004
Revises: 20260813_0003
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260813_0004"
down_revision = "20260813_0003"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())
TIMESTAMPTZ = sa.DateTime(timezone=True)
NOW = sa.text("CURRENT_TIMESTAMP")


def _audit_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=NOW),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False, server_default=NOW),
    ]


def upgrade() -> None:
    op.create_table(
        "decisions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("aggregate_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("decision_type", sa.String(40), nullable=False),
        sa.Column("subject_type", sa.String(40), nullable=False),
        sa.Column("subject_id", UUID, nullable=False),
        sa.Column("case_id", UUID, nullable=False),
        sa.Column("scope_fingerprint", sa.CHAR(64), nullable=False),
        sa.Column("decision_key_hash", sa.CHAR(64), nullable=False),
        sa.Column("cycle_number", sa.Integer(), nullable=False),
        sa.Column("lifecycle", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("validity", sa.String(32), nullable=False),
        sa.Column("condition_status", sa.String(32), nullable=False),
        sa.Column("context_status", sa.String(32), nullable=False),
        sa.Column("selected_final_context_id", UUID, nullable=True),
        sa.Column("successor_decision_id", UUID, nullable=True),
        sa.Column("final_justification", sa.Text(), nullable=True),
        sa.Column("finalized_by_actor_id", UUID, nullable=True),
        sa.Column("finalized_at", TIMESTAMPTZ, nullable=True),
        sa.Column("review_required_reason", sa.Text(), nullable=True),
        sa.Column("review_required_at", TIMESTAMPTZ, nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("cancelled_at", TIMESTAMPTZ, nullable=True),
        sa.Column("created_by_actor_id", UUID, nullable=True),
        sa.Column("updated_by_actor_id", UUID, nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_decisions__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_decisions__cases__tenant_case_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "successor_decision_id"],
            ["decisions.tenant_id", "decisions.id"],
            name="fk_decisions__decisions__tenant_successor_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_decisions__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "decision_key_hash",
            "cycle_number",
            name="uq_decisions__tenant_key_cycle",
        ),
        sa.CheckConstraint(
            "decision_type IN ("
            "'GO_NO_GO', 'RISK_ACCEPTANCE', 'PARTNER_SELECTION', "
            "'PRICING_APPROVAL', 'SUBMISSION_AUTHORIZATION'"
            ")",
            name="decision_type",
        ),
        sa.CheckConstraint("NULLIF(BTRIM(subject_type), '') IS NOT NULL", name="subject_type"),
        sa.CheckConstraint("cycle_number > 0", name="positive_cycle_number"),
        sa.CheckConstraint(
            "lifecycle IN ('DRAFT', 'PENDING_PATRON', 'FINALIZED', 'SUPERSEDED', 'CANCELLED')",
            name="lifecycle",
        ),
        sa.CheckConstraint(
            "outcome IN ("
            "'UNDECIDED', 'GO', 'CONDITIONAL_GO', 'NO_GO', 'ACCEPTED', "
            "'REJECTED', 'AUTHORIZED', 'NOT_AUTHORIZED'"
            ")",
            name="outcome",
        ),
        sa.CheckConstraint(
            "validity IN ('CURRENT', 'REVIEW_REQUIRED', 'SUPERSEDED', 'INVALIDATED')",
            name="validity",
        ),
        sa.CheckConstraint(
            "condition_status IN ('NOT_APPLICABLE', 'OPEN', 'SATISFIED', 'FAILED', 'WAIVED')",
            name="condition_status",
        ),
        sa.CheckConstraint(
            "context_status IN ('INCOMPLETE', 'FROZEN', 'STALE')",
            name="context_status",
        ),
        sa.CheckConstraint(
            "lifecycle <> 'FINALIZED' OR ("
            "outcome <> 'UNDECIDED' AND selected_final_context_id IS NOT NULL "
            "AND final_justification IS NOT NULL AND finalized_by_actor_id IS NOT NULL "
            "AND finalized_at IS NOT NULL"
            ")",
            name="finalization_required_fields",
        ),
        sa.CheckConstraint(
            "outcome <> 'CONDITIONAL_GO' OR condition_status <> 'NOT_APPLICABLE'",
            name="conditional_go_requires_condition_status",
        ),
        sa.CheckConstraint(
            "lifecycle <> 'SUPERSEDED' OR ("
            "successor_decision_id IS NOT NULL AND successor_decision_id <> id "
            "AND validity = 'SUPERSEDED'"
            ")",
            name="superseded_requires_successor",
        ),
        sa.CheckConstraint(
            "validity <> 'REVIEW_REQUIRED' OR ("
            "review_required_reason IS NOT NULL AND review_required_at IS NOT NULL"
            ")",
            name="review_required_reason",
        ),
        sa.CheckConstraint(
            "lifecycle <> 'CANCELLED' OR (cancel_reason IS NOT NULL AND cancelled_at IS NOT NULL)",
            name="cancel_reason_when_cancelled",
        ),
    )
    op.create_index("ix_decisions_tenant_id", "decisions", ["tenant_id"])
    op.create_index(
        "ix_decisions__tenant_case_type_lifecycle",
        "decisions",
        ["tenant_id", "case_id", "decision_type", "lifecycle"],
    )
    op.create_index(
        "ix_decisions__tenant_validity_updated",
        "decisions",
        ["tenant_id", "validity", sa.text("updated_at DESC")],
    )

    op.create_table(
        "decision_contexts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("decision_id", UUID, nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("context_fingerprint", sa.CHAR(64), nullable=False),
        sa.Column("canonical_context_json", JSONB, nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("unknowns_json", JSONB, nullable=False),
        sa.Column("prepared_at", TIMESTAMPTZ, nullable=False),
        sa.Column("context_state", sa.String(32), nullable=False),
        sa.Column("is_selected_final", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("prepared_by_actor_id", UUID, nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "decision_id"],
            ["decisions.tenant_id", "decisions.id"],
            name="fk_decision_contexts__decisions__tenant_decision_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_decision_contexts__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "decision_id",
            "id",
            name="uq_decision_contexts__tenant_decision_id",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "decision_id",
            "sequence_number",
            name="uq_decision_contexts__tenant_decision_sequence",
        ),
        sa.CheckConstraint("sequence_number > 0", name="positive_sequence_number"),
        sa.CheckConstraint("context_state IN ('DRAFT', 'FROZEN')", name="context_state"),
    )
    op.create_index("ix_decision_contexts_tenant_id", "decision_contexts", ["tenant_id"])
    op.create_index(
        "ux_decision_contexts__selected_final",
        "decision_contexts",
        ["tenant_id", "decision_id"],
        unique=True,
        postgresql_where=sa.text("is_selected_final"),
    )
    op.create_foreign_key(
        "fk_decisions__contexts__selected_final_context_id",
        "decisions",
        "decision_contexts",
        ["tenant_id", "id", "selected_final_context_id"],
        ["tenant_id", "decision_id", "id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "decision_context_references",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("decision_context_id", UUID, nullable=False),
        sa.Column("aggregate_type", sa.String(80), nullable=False),
        sa.Column("aggregate_id", UUID, nullable=False),
        sa.Column("aggregate_revision", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.CHAR(64), nullable=True),
        sa.Column("reference_role", sa.String(80), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "decision_context_id"],
            ["decision_contexts.tenant_id", "decision_contexts.id"],
            name="fk_decision_context_refs__contexts__tenant_context_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_decision_context_references__tenant_id",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "decision_context_id",
            "aggregate_type",
            "aggregate_id",
            "reference_role",
            name="uq_decision_context_refs__identity",
        ),
        sa.CheckConstraint("NULLIF(BTRIM(aggregate_type), '') IS NOT NULL", name="aggregate_type"),
        sa.CheckConstraint("aggregate_revision >= 0", name="non_negative_revision"),
        sa.CheckConstraint("NULLIF(BTRIM(reference_role), '') IS NOT NULL", name="reference_role"),
    )
    op.create_index(
        "ix_decision_context_references_tenant_id",
        "decision_context_references",
        ["tenant_id"],
    )
    op.create_index(
        "ix_decision_context_refs__tenant_aggregate",
        "decision_context_references",
        ["tenant_id", "aggregate_type", "aggregate_id"],
    )

    op.create_table(
        "decision_conditions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("decision_id", UUID, nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("owner_actor_id", UUID, nullable=True),
        sa.Column("due_at", TIMESTAMPTZ, nullable=True),
        sa.Column("due_date_absence_reason", sa.Text(), nullable=True),
        sa.Column("failure_consequence", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("satisfied_evidence_ref_json", JSONB, nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("waiver_justification", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "decision_id"],
            ["decisions.tenant_id", "decisions.id"],
            name="fk_decision_conditions__decisions__tenant_decision_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_decision_conditions__tenant_id"),
        sa.CheckConstraint(
            "due_at IS NOT NULL OR NULLIF(BTRIM(due_date_absence_reason), '') IS NOT NULL",
            name="deadline_or_reason",
        ),
        sa.CheckConstraint(
            "NULLIF(BTRIM(failure_consequence), '') IS NOT NULL",
            name="failure_consequence",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'SATISFIED', 'FAILED', 'WAIVED')",
            name="status",
        ),
    )
    op.create_index("ix_decision_conditions_tenant_id", "decision_conditions", ["tenant_id"])
    op.create_index(
        "ix_decision_conditions__tenant_decision",
        "decision_conditions",
        ["tenant_id", "decision_id"],
    )

    op.execute(
        """
        CREATE FUNCTION protect_frozen_decision_context() RETURNS trigger AS $$
        BEGIN
          IF OLD.context_state = 'FROZEN' OR OLD.is_selected_final THEN
            IF OLD.context_fingerprint IS DISTINCT FROM NEW.context_fingerprint
               OR OLD.canonical_context_json IS DISTINCT FROM NEW.canonical_context_json
               OR OLD.rationale IS DISTINCT FROM NEW.rationale THEN
              RAISE EXCEPTION 'DECISION_CONTEXT_IMMUTABLE';
            END IF;
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_decision_contexts_immutable_content
        BEFORE UPDATE ON decision_contexts
        FOR EACH ROW EXECUTE FUNCTION protect_frozen_decision_context();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_decision_contexts_immutable_content ON decision_contexts"
    )
    op.execute("DROP FUNCTION IF EXISTS protect_frozen_decision_context()")
    op.drop_index(
        "ix_decision_conditions__tenant_decision",
        table_name="decision_conditions",
    )
    op.drop_index(
        "ix_decision_conditions_tenant_id",
        table_name="decision_conditions",
    )
    op.drop_table("decision_conditions")
    op.drop_index(
        "ix_decision_context_refs__tenant_aggregate",
        table_name="decision_context_references",
    )
    op.execute("DROP INDEX IF EXISTS ix_decision_context_references_tenant_id")
    op.drop_table("decision_context_references")
    op.drop_constraint(
        "fk_decisions__contexts__selected_final_context_id",
        "decisions",
        type_="foreignkey",
    )
    op.drop_index(
        "ux_decision_contexts__selected_final",
        table_name="decision_contexts",
    )
    op.drop_index(
        "ix_decision_contexts_tenant_id",
        table_name="decision_contexts",
    )
    op.drop_table("decision_contexts")
    op.drop_index("ix_decisions__tenant_validity_updated", table_name="decisions")
    op.drop_index(
        "ix_decisions__tenant_case_type_lifecycle",
        table_name="decisions",
    )
    op.drop_index("ix_decisions_tenant_id", table_name="decisions")
    op.drop_table("decisions")
