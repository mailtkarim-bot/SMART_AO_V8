"""Persistence records for auditable BOAMP observation ingestion."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, TenantScopedRecord


class BoampIngestionRunRecord(TenantScopedRecord, Base):
    __tablename__ = "boamp_ingestion_runs"
    __table_args__ = (
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="boamp_ingestion_runs_tenant"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "actor_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.identity_id"],
            name="boamp_ingestion_runs_actor",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "profile_id"],
            ["opportunity_watch_profiles.tenant_id", "opportunity_watch_profiles.id"],
            name="boamp_ingestion_runs_profile",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "profile_id", "profile_version"],
            [
                "opportunity_watch_profile_versions.tenant_id",
                "opportunity_watch_profile_versions.profile_id",
                "opportunity_watch_profile_versions.version_number",
            ],
            name="boamp_ingestion_runs_profile_version",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_boamp_ingestion_runs_tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_boamp_ingestion_runs_command"),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_boamp_ingestion_runs_idempotency"
        ),
        sa.CheckConstraint(
            "status IN ('RECORDED', 'REJECTED')", name="boamp_ingestion_runs_status"
        ),
        sa.CheckConstraint("profile_version >= 1", name="boamp_ingestion_runs_profile_version"),
        sa.CheckConstraint("pages_read >= 0", name="boamp_ingestion_runs_pages_read"),
        sa.CheckConstraint("candidate_count >= 0", name="boamp_ingestion_runs_candidate_count"),
        sa.CheckConstraint(
            "request_hash ~ '^[a-f0-9]{64}$'", name="boamp_ingestion_runs_request_hash"
        ),
        sa.Index("ix_boamp_ingestion_runs_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    profile_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    profile_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    request_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, server_default="RECORDED")
    pages_read: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    candidate_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    truncated: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.false())
    started_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class BoampOpportunityObservationRecord(TenantScopedRecord, Base):
    __tablename__ = "boamp_opportunity_observations"
    __table_args__ = (
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="boamp_observations_tenant"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_boamp_observations_tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "source", "source_notice_id", "fingerprint_sha256",
            name="uq_boamp_observations_source_fingerprint",
        ),
        sa.CheckConstraint("source = 'BOAMP'", name="boamp_observations_source"),
        sa.CheckConstraint(
            "fingerprint_sha256 ~ '^[a-f0-9]{64}$'", name="boamp_observations_fingerprint"
        ),
        sa.CheckConstraint("score BETWEEN 0 AND 100", name="boamp_observations_score"),
        sa.CheckConstraint(
            "score_explanation_sha256 ~ '^[a-f0-9]{64}$'",
            name="boamp_observations_score_explanation_hash",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(score_explanation_json) = 'object'",
            name="boamp_observations_score_explanation_object",
        ),
        sa.Index(
            "ix_boamp_observations_tenant_source_notice",
            "tenant_id",
            "source",
            "source_notice_id",
        ),
        sa.Index(
            "ix_boamp_observations_tenant_deadline",
            "tenant_id",
            "response_deadline",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    source: Mapped[str] = mapped_column(sa.String(24), nullable=False, server_default="BOAMP")
    source_notice_id: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    fingerprint_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    title: Mapped[str | None] = mapped_column(sa.String(500))
    publication_date: Mapped[date | None] = mapped_column(sa.Date)
    response_deadline: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    department_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    market_types: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    source_status: Mapped[str | None] = mapped_column(sa.String(64))
    score_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    score: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    score_explanation_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    score_explanation_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class BoampOpportunityQualificationRecord(TenantScopedRecord, Base):
    __tablename__ = "boamp_opportunity_qualifications"
    __table_args__ = (
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="boamp_qualifications_tenant"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "actor_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.identity_id"],
            name="boamp_qualifications_actor",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "observation_id"],
            ["boamp_opportunity_observations.tenant_id", "boamp_opportunity_observations.id"],
            name="boamp_qualifications_observation",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_boamp_qualifications_tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_boamp_qualifications_command"),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_boamp_qualifications_idempotency"
        ),
        sa.CheckConstraint(
            "decision IN ('QUALIFIED', 'REJECTED', 'SNOOZED')",
            name="boamp_qualifications_decision",
        ),
        sa.CheckConstraint(
            "reason_code IN ('RELEVANT_PUBLIC_SIGNAL', 'NOT_RELEVANT', "
            "'INSUFFICIENT_PUBLIC_DATA', 'EXPIRED')",
            name="boamp_qualifications_reason",
        ),
        sa.CheckConstraint("score_snapshot BETWEEN 0 AND 100", name="boamp_qualifications_score"),
        sa.CheckConstraint(
            "score_version = 'BOAMP_PUBLIC_V1'", name="boamp_qualifications_score_version"
        ),
        sa.Index(
            "ix_boamp_qualifications_tenant_observation_created",
            "tenant_id",
            "observation_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    observation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    decision: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    reason_code: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    score_snapshot: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    score_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class BoampIngestionObservationLinkRecord(TenantScopedRecord, Base):
    __tablename__ = "boamp_ingestion_observation_links"
    __table_args__ = (
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="boamp_links_tenant"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "ingestion_run_id"],
            ["boamp_ingestion_runs.tenant_id", "boamp_ingestion_runs.id"],
            name="boamp_links_run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "observation_id"],
            ["boamp_opportunity_observations.tenant_id", "boamp_opportunity_observations.id"],
            name="boamp_links_observation",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_boamp_links_tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "ingestion_run_id", "observation_id", name="uq_boamp_links_run_observation"
        ),
        sa.Index("ix_boamp_links_tenant_run", "tenant_id", "ingestion_run_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    ingestion_run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    observation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
