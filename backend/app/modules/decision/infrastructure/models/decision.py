"""SQLAlchemy records owned by the Decision aggregate.

The pure aggregate remains under ``decision.domain``. This persistence adapter
stores only the Decision root and its internal contexts, references and
conditions. It intentionally exposes no ORM relationship to mutable external
roots such as Case, Pricing or Submission.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, RevisionedAggregateRecord, TenantScopedRecord


class DecisionRecord(RevisionedAggregateRecord, Base):
    __tablename__ = "decisions"
    __table_args__ = (
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
        sa.ForeignKeyConstraint(
            ["tenant_id", "id", "selected_final_context_id"],
            [
                "decision_contexts.tenant_id",
                "decision_contexts.decision_id",
                "decision_contexts.id",
            ],
            name="fk_decisions__contexts__selected_final_context_id",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_decisions__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "decision_key_hash",
            "cycle_number",
            name="uq_decisions__tenant_key_cycle",
        ),
        sa.Index(
            "ux_decisions__tenant_active_key",
            "tenant_id",
            "decision_key_hash",
            unique=True,
            postgresql_where=sa.text(
                "validity = 'CURRENT' AND lifecycle NOT IN ('SUPERSEDED', 'CANCELLED')"
            ),
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
        sa.Index(
            "ix_decisions__tenant_case_type_lifecycle",
            "tenant_id",
            "case_id",
            "decision_type",
            "lifecycle",
        ),
        sa.Index(
            "ix_decisions__tenant_validity_updated",
            "tenant_id",
            "validity",
            sa.text("updated_at DESC"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    decision_type: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    subject_type: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    subject_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    scope_fingerprint: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    decision_key_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    cycle_number: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    lifecycle: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    validity: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    condition_status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    context_status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    selected_final_context_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )
    successor_decision_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )
    final_justification: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    finalized_by_actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    review_required_reason: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    review_required_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    cancel_reason: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_by_actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    updated_by_actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class DecisionContextRecord(TenantScopedRecord, Base):
    __tablename__ = "decision_contexts"
    __table_args__ = (
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
        sa.Index(
            "ux_decision_contexts__selected_final",
            "tenant_id",
            "decision_id",
            unique=True,
            postgresql_where=sa.text("is_selected_final"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    decision_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    sequence_number: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    context_fingerprint: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    canonical_context_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    rationale: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    unknowns_json: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    prepared_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    context_state: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    is_selected_final: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False)
    prepared_by_actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class DecisionContextReferenceRecord(TenantScopedRecord, Base):
    __tablename__ = "decision_context_references"
    __table_args__ = (
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
        sa.Index(
            "ix_decision_context_refs__tenant_aggregate",
            "tenant_id",
            "aggregate_type",
            "aggregate_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    decision_context_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    aggregate_revision: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(sa.CHAR(64), nullable=True)
    reference_role: Mapped[str] = mapped_column(sa.String(80), nullable=False)


class DecisionConditionTransitionRecord(TenantScopedRecord, Base):
    __tablename__ = "decision_condition_transitions"
    __table_args__ = (
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
            "tenant_id",
            "command_id",
            name="uq_decision_condition_transitions__command",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_decision_condition_transitions__idempotency",
        ),
        sa.CheckConstraint(
            "from_status = 'OPEN' AND to_status IN ('SATISFIED', 'FAILED')",
            name="valid_transition",
        ),
        sa.CheckConstraint("aggregate_revision > 0", name="positive_revision"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    decision_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    condition_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    from_status: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    to_status: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    satisfied_evidence_ref_json: Mapped[dict[str, object] | None] = mapped_column(
        JSONB, nullable=True
    )
    failure_reason: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    aggregate_revision: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class DecisionConditionRecord(TenantScopedRecord, Base):
    __tablename__ = "decision_conditions"
    __table_args__ = (
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
        sa.Index("ix_decision_conditions__tenant_decision", "tenant_id", "decision_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    decision_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    label: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    owner_actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    due_date_absence_reason: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    failure_consequence: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    satisfied_evidence_ref_json: Mapped[dict[str, object] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    failure_reason: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    waiver_justification: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
