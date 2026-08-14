"""Immutable Case-scoped impact register for DCE rectifications."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, TenantScopedRecord


class CaseDceImpactRunRecord(TenantScopedRecord, Base):
    """One deterministic, replay-safe impact computation for a Case and two DCE versions."""

    __tablename__ = "case_dce_impact_runs"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_case_dce_impact_runs__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_case_dce_impact_runs__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "predecessor_dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_case_dce_impact_runs__predecessor",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "successor_dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_case_dce_impact_runs__successor",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_case_dce_impact_runs__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "case_id",
            "predecessor_dce_version_id",
            "successor_dce_version_id",
            "input_manifest_sha256",
            "algorithm_id",
            "algorithm_version",
            name="uq_case_dce_impact_runs__identity",
        ),
        sa.CheckConstraint("status IN ('COMPLETED', 'NO_SIGNAL')", name="status"),
        sa.CheckConstraint("previous_requirement_count >= 0", name="previous_count_nonnegative"),
        sa.CheckConstraint("successor_requirement_count >= 0", name="successor_count_nonnegative"),
        sa.CheckConstraint("failure_code IS NULL", name="failure_code_empty"),
        sa.Index(
            "ix_case_dce_impact_runs__tenant_case_created",
            "tenant_id",
            "case_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    predecessor_dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    successor_dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    input_manifest_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    algorithm_id: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    previous_requirement_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    successor_requirement_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    failure_code: Mapped[str | None] = mapped_column(sa.String(120))
    created_by_actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class CaseDceImpactItemRecord(TenantScopedRecord, Base):
    """One immutable review obligation or successor candidate."""

    __tablename__ = "case_dce_impact_items"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_case_dce_impact_items__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "impact_run_id"],
            ["case_dce_impact_runs.tenant_id", "case_dce_impact_runs.id"],
            name="fk_case_dce_impact_items__run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_case_dce_impact_items__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "previous_requirement_id"],
            ["dce_requirements.tenant_id", "dce_requirements.id"],
            name="fk_case_dce_impact_items__previous_requirement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "successor_requirement_id"],
            ["dce_requirements.tenant_id", "dce_requirements.id"],
            name="fk_case_dce_impact_items__successor_requirement",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_case_dce_impact_items__tenant_id"),
        sa.CheckConstraint(
            "impact_kind IN ('DCE_VERSION_REPLACED', 'PREVIOUS_REQUIREMENT_REQUIRES_REVIEW', "
            "'SUCCESSOR_REQUIREMENT_CANDIDATE', 'VERSION_HAS_NO_MATERIALIZED_SIGNAL')",
            name="impact_kind",
        ),
        sa.CheckConstraint(
            "review_state IN ('REVIEW_REQUIRED', 'PENDING_HUMAN_REVIEW')", name="review_state"
        ),
        sa.CheckConstraint(
            "evidence_code IN ('RECTIFICATION_CHAIN', 'PREVIOUS_REQUIREMENT', "
            "'SUCCESSOR_REQUIREMENT', 'NO_SIGNAL')",
            name="evidence_code",
        ),
        sa.CheckConstraint(
            "(impact_kind = 'PREVIOUS_REQUIREMENT_REQUIRES_REVIEW' "
            "AND previous_requirement_id IS NOT NULL AND successor_requirement_id IS NULL) OR "
            "(impact_kind = 'SUCCESSOR_REQUIREMENT_CANDIDATE' "
            "AND previous_requirement_id IS NULL AND successor_requirement_id IS NOT NULL) OR "
            "(impact_kind IN ('DCE_VERSION_REPLACED', 'VERSION_HAS_NO_MATERIALIZED_SIGNAL') "
            "AND previous_requirement_id IS NULL AND successor_requirement_id IS NULL)",
            name="requirement_reference_shape",
        ),
        sa.Index(
            "ix_case_dce_impact_items__tenant_run",
            "tenant_id",
            "impact_run_id",
        ),
        sa.Index(
            "ix_case_dce_impact_items__tenant_case",
            "tenant_id",
            "case_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    impact_run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    impact_kind: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    previous_requirement_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    successor_requirement_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    review_state: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    evidence_code: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
