"""Tenant-scoped durable registry for DCE objects before immutable admission."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, TenantScopedRecord


class DceStagedObjectRecord(TenantScopedRecord, Base):
    """Private staging ledger; its storage key is never a public response field."""

    __tablename__ = "dce_staged_objects"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_dce_staged_objects__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "consultation_id"],
            ["consultations.tenant_id", "consultations.id"],
            name="fk_dce_staged_objects__consultations__tenant_consultation_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "consumed_by_dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_staged_objects__dce_versions__tenant_consumed_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_staged_objects__tenant_id"),
        sa.UniqueConstraint("storage_key", name="uq_dce_staged_objects__storage_key"),
        sa.CheckConstraint("expected_byte_size > 0", name="expected_byte_size_positive"),
        sa.CheckConstraint(
            "actual_byte_size IS NULL OR actual_byte_size > 0",
            name="actual_byte_size_positive",
        ),
        sa.CheckConstraint(
            "sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'",
            name="sha256_lowercase",
        ),
        sa.CheckConstraint(
            "state IN ('AWAITING_UPLOAD', 'UPLOADING', 'QUARANTINED', 'CLEAN', "
            "'REJECTED', 'CONSUMED', 'EXPIRED')",
            name="state",
        ),
        sa.CheckConstraint(
            "scan_verdict IS NULL OR scan_verdict IN ('CLEAN', 'INFECTED', 'ERROR')",
            name="scan_verdict",
        ),
        sa.CheckConstraint(
            "state <> 'CONSUMED' OR "
            "(consumed_by_dce_version_id IS NOT NULL AND consumed_at IS NOT NULL)",
            name="consumed_fields_required",
        ),
        sa.CheckConstraint(
            "state = 'CONSUMED' OR "
            "(consumed_by_dce_version_id IS NULL AND consumed_at IS NULL)",
            name="consumed_fields_only_when_consumed",
        ),
        sa.CheckConstraint(
            "state <> 'CLEAN' OR "
            "(actual_byte_size IS NOT NULL AND sha256 IS NOT NULL AND media_type IS NOT NULL "
            "AND scan_verdict = 'CLEAN' AND scanner_name IS NOT NULL "
            "AND scanner_signature_version IS NOT NULL AND scanned_at IS NOT NULL)",
            name="clean_metadata_required",
        ),
        sa.Index(
            "ix_dce_staged_objects__tenant_consultation_state",
            "tenant_id",
            "consultation_id",
            "state",
        ),
        sa.Index(
            "ix_dce_staged_objects__tenant_expiry",
            "tenant_id",
            "expires_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    consultation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    storage_key: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    original_filename: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    expected_byte_size: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    actual_byte_size: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    sha256: Mapped[str | None] = mapped_column(sa.CHAR(64), nullable=True)
    media_type: Mapped[str | None] = mapped_column(sa.String(180), nullable=True)
    source_channel: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    scan_verdict: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    scanner_name: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    scanner_signature_version: Mapped[str | None] = mapped_column(sa.String(240), nullable=True)
    scanned_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    rejection_code: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    consumed_by_dce_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    consumed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_by_actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    updated_by_actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
