"""Immutable atomic requirements materialized from completed RC analysis observations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, TenantScopedRecord


class DceRequirementMaterializationRunRecord(TenantScopedRecord, Base):
    __tablename__ = "dce_requirement_materialization_runs"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_dce_req_runs__tenants", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_req_runs__version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_rc_analysis_id"],
            ["dce_rc_analysis_runs.tenant_id", "dce_rc_analysis_runs.id"],
            name="fk_dce_req_runs__analysis",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uq_dce_requirement_materialization_runs__tenant_id"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "dce_version_id",
            "dce_rc_analysis_id",
            "input_manifest_sha256",
            "materializer_id",
            "materializer_version",
            name="uq_dce_req_run_identity",
        ),
        sa.CheckConstraint(
            "status IN ('COMPLETED', 'NO_SIGNAL', 'REJECTED_LIMIT', 'FAILED_SAFE')", name="status"
        ),
        sa.CheckConstraint("source_observation_count >= 0", name="source_obs_nonneg"),
        sa.CheckConstraint(
            "(status IN ('COMPLETED', 'NO_SIGNAL') AND failure_code IS NULL) OR "
            "(status NOT IN ('COMPLETED', 'NO_SIGNAL') AND failure_code IS NOT NULL)",
            name="status_failure_code",
        ),
        sa.Index(
            "ix_dce_req_runs__tenant_version_created", "tenant_id", "dce_version_id", "created_at"
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dce_rc_analysis_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    input_manifest_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    materializer_id: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    materializer_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    source_observation_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    failure_code: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class DceRequirementRecord(TenantScopedRecord, Base):
    __tablename__ = "dce_requirements"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_dce_requirements__tenants", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "requirements_run_id"],
            [
                "dce_requirement_materialization_runs.tenant_id",
                "dce_requirement_materialization_runs.id",
            ],
            name="fk_dce_requirements__run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_requirements__version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "source_observation_id"],
            ["dce_rc_requirement_observations.tenant_id", "dce_rc_requirement_observations.id"],
            name="fk_dce_requirements__observation",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_requirements__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "requirements_run_id",
            "source_observation_id",
            name="uq_dce_requirement_source_obs",
        ),
        sa.CheckConstraint(
            "requirement_type IN ('CANDIDATURE_DOCUMENT', 'OFFER_DOCUMENT', "
            "'SUBMISSION_DEADLINE_SIGNAL', 'SUBMISSION_CHANNEL', 'FILE_CONSTRAINT', "
            "'SITE_VISIT', 'AWARD_CRITERION_SIGNAL', 'NEGOTIATION_SIGNAL', "
            "'OFFER_VALIDITY_SIGNAL')",
            name="requirement_type",
        ),
        sa.CheckConstraint(
            "directive_signal IN ('REQUIRED_SIGNAL', 'OPTIONAL_SIGNAL', 'UNSPECIFIED')",
            name="directive",
        ),
        sa.CheckConstraint(
            "confirmation_status = 'PENDING_HUMAN_CONFIRMATION'", name="confirmation"
        ),
        sa.CheckConstraint("uncertainty_status = 'SOURCE_SIGNAL_ONLY'", name="uncertainty"),
        sa.Index("ix_dce_requirements__tenant_run", "tenant_id", "requirements_run_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    requirements_run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source_observation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    requirement_type: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    directive_signal: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    confirmation_status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    uncertainty_status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class DceRequirementSourceRecord(TenantScopedRecord, Base):
    __tablename__ = "dce_requirement_sources"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_dce_req_sources__tenants", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "requirement_id"],
            ["dce_requirements.tenant_id", "dce_requirements.id"],
            name="fk_dce_req_sources__requirement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "source_observation_id"],
            ["dce_rc_requirement_observations.tenant_id", "dce_rc_requirement_observations.id"],
            name="fk_dce_req_sources__observation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "fragment_id"],
            ["dce_document_extraction_fragments.tenant_id", "dce_document_extraction_fragments.id"],
            name="fk_dce_req_sources__fragment",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_requirement_sources__tenant_id"),
        sa.UniqueConstraint("tenant_id", "requirement_id", name="uq_dce_req_source_requirement"),
        sa.CheckConstraint("start_byte_offset >= 0", name="start_offset_nonneg"),
        sa.CheckConstraint("end_byte_offset > start_byte_offset", name="offsets_ordered"),
        sa.Index("ix_dce_req_sources__tenant_requirement", "tenant_id", "requirement_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    requirement_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source_observation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    fragment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    start_byte_offset: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    end_byte_offset: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
