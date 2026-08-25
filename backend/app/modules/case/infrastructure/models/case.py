"""SQLAlchemy records owned by the Case aggregate.

The pure aggregate stays under ``case.domain``. This adapter preserves only
Case-owned state and append-only reference histories; it deliberately exposes
no ORM relationship to Decision, Pricing, Task, Submission or Evidence.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, RevisionedAggregateRecord, TenantScopedRecord


class CaseRecord(RevisionedAggregateRecord, Base):
    __tablename__ = "cases"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_cases__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "consultation_id"],
            ["consultations.tenant_id", "consultations.id"],
            name="fk_cases__consultations__tenant_consultation_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "applicable_dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_cases__dce_versions__tenant_applicable_dce_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_cases__tenant_id"),
        sa.CheckConstraint(
            "business_origin IN ('MANUAL', 'OPPORTUNITY', 'IMPORT', 'CLIENT_REQUEST')",
            name="business_origin",
        ),
        sa.CheckConstraint(
            "consultation_id IS NOT NULL OR business_origin = 'MANUAL' OR "
            "(business_origin = 'OPPORTUNITY' AND origin_reference_id IS NOT NULL)",
            name="consultation_required_unless_manual",
        ),
        sa.CheckConstraint(
            "business_origin <> 'MANUAL' OR "
            "NULLIF(BTRIM(origin_rationale), '') IS NOT NULL",
            name="manual_origin_rationale",
        ),
        sa.CheckConstraint(
            "scope_kind IN ('SINGLE_LOT', 'MULTI_LOT', 'TRANCHE', 'VARIANT', 'CUSTOM')",
            name="scope_kind",
        ),
        sa.CheckConstraint(
            "lifecycle IN ('ACTIVE', 'STOPPED', 'ARCHIVED')",
            name="lifecycle",
        ),
        sa.CheckConstraint(
            "commercial_stage IN ("
            "'INTAKE', 'ANALYSIS', 'AWAITING_DECISION', 'OFFER_PREPARATION', "
            "'READY_FOR_PRICING', 'PRICING', 'READY_FOR_FINAL_CONTROL', "
            "'READY_FOR_SUBMISSION', 'SUBMITTED', 'OUTCOME_KNOWN', 'AWARDED', "
            "'EXECUTION'"
            ")",
            name="commercial_stage",
        ),
        sa.CheckConstraint(
            "decision_readiness IN "
            "('NOT_ASSESSED', 'NOT_READY', 'READY_WITH_UNKNOWNS', 'READY')",
            name="decision_readiness",
        ),
        sa.CheckConstraint(
            "dce_freshness IN ('NO_DCE', 'CURRENT', 'REVIEW_REQUIRED')",
            name="dce_freshness",
        ),
        sa.CheckConstraint(
            "responsibility_status IN "
            "('UNASSIGNED', 'ASSIGNED', 'ASSIGNMENT_REVIEW_REQUIRED')",
            name="responsibility_status",
        ),
        sa.CheckConstraint(
            "lifecycle <> 'STOPPED' OR "
            "(stopped_reason IS NOT NULL AND stopped_at IS NOT NULL)",
            name="stopped_reason_when_stopped",
        ),
        sa.CheckConstraint(
            "lifecycle <> 'ARCHIVED' OR "
            "(archived_reason IS NOT NULL AND archived_at IS NOT NULL)",
            name="archived_reason_when_archived",
        ),
        sa.Index(
            "ux_cases__tenant_active_functional_identity",
            "tenant_id",
            "functional_identity_hash",
            unique=True,
            postgresql_where=sa.text("lifecycle <> 'ARCHIVED'"),
        ),
        sa.Index(
            "ix_cases__tenant_lifecycle_stage_updated",
            "tenant_id",
            "lifecycle",
            "commercial_stage",
            sa.text("updated_at DESC"),
        ),
        sa.Index(
            "ix_cases__tenant_applicable_dce_version",
            "tenant_id",
            "applicable_dce_version_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    functional_identity_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    object_description: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    business_origin: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    origin_reference_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    origin_rationale: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    consultation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    scope_kind: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    scope_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    scope_fingerprint: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    applicable_dce_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )
    lifecycle: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    commercial_stage: Mapped[str] = mapped_column(sa.String(48), nullable=False)
    decision_readiness: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    dce_freshness: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    responsibility_status: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    stopped_reason: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    archived_reason: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_by_actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    updated_by_actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class CaseConsultationLinkRecord(TenantScopedRecord, Base):
    __tablename__ = "case_consultation_links"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_case_consultation_links__cases__tenant_case_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "consultation_id"],
            ["consultations.tenant_id", "consultations.id"],
            name="fk_case_consult_links__consultation",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_case_consultation_links__tenant_id"),
        sa.Index(
            "ux_case_consultation_links__current_case",
            "tenant_id",
            "case_id",
            unique=True,
            postgresql_where=sa.text("is_current"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    consultation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    scope_snapshot_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    rationale: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    is_current: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    created_by_actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class CaseDceApplicabilityHistoryRecord(TenantScopedRecord, Base):
    __tablename__ = "case_dce_applicability_history"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_case_dce_history__cases__tenant_case_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_case_dce_history__dce_versions__tenant_dce_version_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_case_dce_applicability_history__tenant_id",
        ),
        sa.Index(
            "ux_case_dce_history__current_case",
            "tenant_id",
            "case_id",
            unique=True,
            postgresql_where=sa.text("is_current"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    is_current: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    set_by_actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    set_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
