"""Immutable deterministic extraction records owned by admitted DCE documents."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, TenantScopedRecord


class DceDocumentExtractionRecord(TenantScopedRecord, Base):
    __tablename__ = "dce_document_extractions"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_dce_document_extractions__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_extract__dce_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_document_id"],
            ["dce_documents.tenant_id", "dce_documents.id"],
            name="fk_dce_extract__dce_document",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_extract__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "dce_document_id",
            "input_sha256",
            "extractor_id",
            "extractor_version",
            name="uq_dce_extract__document_input_extractor",
        ),
        sa.CheckConstraint(
            "status IN ('COMPLETED', 'UNSUPPORTED', 'REJECTED_LIMIT', 'FAILED_SAFE')",
            name="status",
        ),
        sa.CheckConstraint("fragment_count >= 0", name="fragment_count_nonnegative"),
        sa.CheckConstraint("extracted_char_count >= 0", name="char_count_nonnegative"),
        sa.CheckConstraint(
            "(status = 'COMPLETED' AND failure_code IS NULL) OR "
            "(status <> 'COMPLETED' AND failure_code IS NOT NULL)",
            name="status_failure_code",
        ),
        sa.Index(
            "ix_dce_extract__tenant_document_created",
            "tenant_id",
            "dce_document_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dce_document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    input_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    extractor_id: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    extractor_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    fragment_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    extracted_char_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    failure_code: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class DceDocumentExtractionFragmentRecord(TenantScopedRecord, Base):
    __tablename__ = "dce_document_extraction_fragments"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_dce_document_extraction_fragments__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "extraction_id"],
            ["dce_document_extractions.tenant_id", "dce_document_extractions.id"],
            name="fk_dce_extract_frag__extraction",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_extract_frag__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "extraction_id",
            "ordinal",
            name="uq_dce_extract_frag__ordinal",
        ),
        sa.CheckConstraint("ordinal > 0", name="ordinal_positive"),
        sa.CheckConstraint("char_length(text) > 0", name="text_nonempty"),
        sa.Index("ix_dce_extract_frag__tenant_extraction", "tenant_id", "extraction_id", "ordinal"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    extraction_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    locator_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    text: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    text_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
