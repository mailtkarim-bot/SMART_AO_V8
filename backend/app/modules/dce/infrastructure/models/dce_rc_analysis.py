"""Immutable deterministic RC analysis records derived from DCE extraction fragments."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, TenantScopedRecord


class DceRcAnalysisRunRecord(TenantScopedRecord, Base):
    """One terminal deterministic RC analysis over a canonical fragment manifest."""

    __tablename__ = "dce_rc_analysis_runs"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_dce_rc_analysis_runs__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_rc_analysis_runs__dce_versions__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_rc_analysis_runs__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "dce_version_id",
            "input_manifest_sha256",
            "analyzer_id",
            "analyzer_version",
            name="uq_dce_rc_analysis_run_identity",
        ),
        sa.CheckConstraint(
            "status IN ('COMPLETED', 'NO_RC_MARKER', 'REJECTED_LIMIT', 'FAILED_SAFE')",
            name="status",
        ),
        sa.CheckConstraint("source_fragment_count > 0", name="source_fragment_count_positive"),
        sa.CheckConstraint("source_char_count > 0", name="source_char_count_positive"),
        sa.CheckConstraint(
            "(status = 'COMPLETED' AND failure_code IS NULL) OR "
            "(status <> 'COMPLETED' AND failure_code IS NOT NULL)",
            name="status_failure_code",
        ),
        sa.Index(
            "ix_dce_rc_analysis__tenant_version_created",
            "tenant_id",
            "dce_version_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    input_manifest_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    analyzer_id: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    analyzer_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    source_fragment_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    source_char_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    failure_code: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class DceRcRequirementObservationRecord(TenantScopedRecord, Base):
    """One immutable lexical requirement signal recorded by an RC analysis run."""

    __tablename__ = "dce_rc_requirement_observations"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_dce_rc_requirement_observations__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "analysis_id"],
            ["dce_rc_analysis_runs.tenant_id", "dce_rc_analysis_runs.id"],
            name="fk_dce_rc_req_obs__analysis",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_rc_req_obs__version",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uq_dce_rc_requirement_observations__tenant_id"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "analysis_id",
            "rule_id",
            "fragment_id",
            "start_byte_offset",
            "end_byte_offset",
            name="uq_dce_rc_req_obs_identity",
        ),
        sa.CheckConstraint(
            "requirement_kind IN ("
            "'RC_DOCUMENT_CANDIDATURE', 'RC_CONTENT_OFFER', 'RC_SUBMISSION_DEADLINE', "
            "'RC_RESPONSE_CHANNEL', 'RC_FILE_CONSTRAINT', 'RC_SITE_VISIT', "
            "'RC_AWARD_CRITERION', 'RC_NEGOTIATION', 'RC_OFFER_VALIDITY', "
            "'CCAP_PENALTIES', 'CCAP_RETENTION_GUARANTEE', 'CCAP_GUARANTEE', "
            "'CCAP_INSURANCE', 'CCTP_VARIANTS', 'CCAP_SUBCONTRACTING', "
            "'CCAP_QUALIFICATIONS'"
            ")",
            name="requirement_kind",
        ),
        sa.CheckConstraint(
            "directive IN ('REQUIRED_SIGNAL', 'OPTIONAL_SIGNAL', 'UNSPECIFIED')",
            name="directive",
        ),
        sa.CheckConstraint("char_length(excerpt) > 0", name="excerpt_nonempty"),
        sa.Index("ix_dce_rc_req_obs__tenant_analysis", "tenant_id", "analysis_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    analysis_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    requirement_kind: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    directive: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    rule_id: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    rule_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    fragment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    start_byte_offset: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    end_byte_offset: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    excerpt: Mapped[str] = mapped_column(sa.String(1_000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class DceRcRequirementSourceRecord(TenantScopedRecord, Base):
    """One immutable source proof linking an RC observation to an extraction fragment."""

    __tablename__ = "dce_rc_requirement_sources"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_dce_rc_requirement_sources__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "observation_id"],
            ["dce_rc_requirement_observations.tenant_id", "dce_rc_requirement_observations.id"],
            name="fk_dce_rc_req_source__observation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "fragment_id"],
            ["dce_document_extraction_fragments.tenant_id", "dce_document_extraction_fragments.id"],
            name="fk_dce_rc_req_source__fragment",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_rc_requirement_sources__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "observation_id",
            "fragment_id",
            name="uq_dce_rc_req_source_identity",
        ),
        sa.CheckConstraint("start_byte_offset >= 0", name="start_offset_nonnegative"),
        sa.CheckConstraint("end_byte_offset > start_byte_offset", name="offsets_ordered"),
        sa.Index("ix_dce_rc_req_source__tenant_observation", "tenant_id", "observation_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    observation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    fragment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    start_byte_offset: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    end_byte_offset: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
