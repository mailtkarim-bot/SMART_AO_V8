"""Immutable, tenant-scoped CCAP/CCTP risk register records."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, TenantScopedRecord


class DecisionRiskRecord(TenantScopedRecord, Base):
    """One patron-owned structured risk linked to a versioned DCE fragment."""

    __tablename__ = "decision_risks"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_decision_risks__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_decision_risks__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_decision_risks__dce_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "source_fragment_id"],
            ["dce_document_extraction_fragments.tenant_id", "dce_document_extraction_fragments.id"],
            name="fk_decision_risks__source_fragment",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_decision_risks__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "functional_key", name="uq_decision_risks__functional_key"
        ),
        sa.CheckConstraint("category IN ('CCAP', 'CCTP')", name="category"),
        sa.CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name="severity"
        ),
        sa.CheckConstraint(
            "likelihood IN ('RARE', 'POSSIBLE', 'LIKELY', 'ALMOST_CERTAIN')", name="likelihood"
        ),
        sa.CheckConstraint("treatment IN ('OPEN', 'ACCEPTED', 'MITIGATED')", name="treatment"),
        sa.CheckConstraint("char_length(btrim(title)) > 0", name="title_nonempty"),
        sa.CheckConstraint("char_length(btrim(statement)) > 0", name="statement_nonempty"),
        sa.CheckConstraint(
            "char_length(btrim(source_excerpt)) > 0", name="source_excerpt_nonempty"
        ),
        sa.CheckConstraint("start_byte_offset >= 0", name="start_offset_nonnegative"),
        sa.CheckConstraint("end_byte_offset > start_byte_offset", name="offsets_ordered"),
        sa.Index("ix_decision_risks__tenant_case", "tenant_id", "case_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source_fragment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    functional_key: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    category: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    risk_code: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    statement: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    severity: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    likelihood: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    treatment: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="OPEN")
    source_excerpt: Mapped[str] = mapped_column(sa.String(2_000), nullable=False)
    source_locator_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    start_byte_offset: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    end_byte_offset: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    due_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class DecisionRiskTreatmentTransitionRecord(TenantScopedRecord, Base):
    """Immutable treatment transition with patron evidence."""

    __tablename__ = "decision_risk_treatment_transitions"
    __table_args__ = (
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
        sa.UniqueConstraint("tenant_id", "id", name="uq_decision_risk_transitions__tenant_id"),
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
        sa.Index(
            "ix_decision_risk_transitions__tenant_risk_revision",
            "tenant_id",
            "risk_id",
            "aggregate_revision",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    risk_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    from_treatment: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    to_treatment: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    evidence_excerpt: Mapped[str] = mapped_column(sa.String(2_000), nullable=False)
    evidence_locator_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    evidence_start_byte_offset: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    evidence_end_byte_offset: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    rationale: Mapped[str] = mapped_column(sa.String(2_000), nullable=False)
    aggregate_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
