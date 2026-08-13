"""SQLAlchemy records owned by the DceVersion aggregate.

The records preserve originals and source anchors. They never store analytical
requirements, SourceAssertions, pricing, Case or Decision objects.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, RevisionedAggregateRecord, TenantScopedRecord


class DceVersionRecord(RevisionedAggregateRecord, Base):
    __tablename__ = "dce_versions"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_dce_versions__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "consultation_id"],
            ["consultations.tenant_id", "consultations.id"],
            name="fk_dce_versions__consultations__tenant_consultation_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "predecessor_dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_versions__dce_versions__tenant_predecessor_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_versions__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "consultation_id",
            "corpus_hash",
            name="uq_dce_versions__tenant_consultation_corpus_hash",
        ),
        sa.CheckConstraint(
            "lifecycle IN ('ADMITTED', 'SUPERSEDED', 'WITHDRAWN')",
            name="lifecycle",
        ),
        sa.CheckConstraint(
            "integrity IN ('VERIFIED', 'PARTIAL', 'UNUSABLE')",
            name="integrity",
        ),
        sa.CheckConstraint(
            "classification_readiness IN "
            "('UNCLASSIFIED', 'PARTIALLY_CLASSIFIED', 'CLASSIFIED')",
            name="classification_readiness",
        ),
        sa.CheckConstraint(
            "analysis_readiness IN ('NOT_READY', 'READY_FOR_ANALYSIS', 'REVIEW_REQUIRED')",
            name="analysis_readiness",
        ),
        sa.CheckConstraint(
            "lifecycle <> 'WITHDRAWN' OR "
            "(withdrawal_source IS NOT NULL AND withdrawal_reason IS NOT NULL)",
            name="withdrawal_source_when_withdrawn",
        ),
        sa.Index(
            "ix_dce_versions__tenant_consultation_received",
            "tenant_id",
            "consultation_id",
            sa.text("source_received_at DESC"),
        ),
        sa.Index(
            "ix_dce_versions__tenant_predecessor",
            "tenant_id",
            "predecessor_dce_version_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    consultation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    corpus_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    predecessor_dce_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    provenance_channel: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    provenance_reference: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    provenance_url: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    source_received_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    lifecycle: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    integrity: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    classification_readiness: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    analysis_readiness: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    withdrawal_source: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    withdrawal_reason: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    withdrawn_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    created_by_actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    updated_by_actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class DceDocumentRecord(TenantScopedRecord, Base):
    __tablename__ = "dce_documents"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_documents__dce_versions__tenant_dce_version_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "storage_object_id"],
            ["dce_staged_objects.tenant_id", "dce_staged_objects.id"],
            name="fk_dce_documents__dce_staged_objects__tenant_storage_object_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_documents__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "dce_version_id",
            "sha256",
            name="uq_dce_documents__tenant_dce_version_sha256",
        ),
        sa.CheckConstraint("byte_size > 0", name="byte_size_positive"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    storage_object_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    storage_key: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    original_filename: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    media_type: Mapped[str] = mapped_column(sa.String(180), nullable=False)
    byte_size: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    received_from: Mapped[str] = mapped_column(sa.String(240), nullable=False)


class DceDocumentClassificationRecord(TenantScopedRecord, Base):
    __tablename__ = "dce_document_classifications"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_document_id"],
            ["dce_documents.tenant_id", "dce_documents.id"],
            name="fk_dce_doc_class__document",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "previous_classification_id"],
            ["dce_document_classifications.tenant_id", "dce_document_classifications.id"],
            name="fk_dce_doc_class__previous",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uq_dce_document_classifications__tenant_id"
        ),
        sa.Index(
            "ux_dce_document_classifications__current_document",
            "tenant_id",
            "dce_document_id",
            unique=True,
            postgresql_where=sa.text("is_current"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    dce_document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    classification: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    rationale: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    source: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    previous_classification_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    is_current: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    created_by_actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class DceDocumentIssueRecord(TenantScopedRecord, Base):
    __tablename__ = "dce_document_issues"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_doc_issues__version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_document_id"],
            ["dce_documents.tenant_id", "dce_documents.id"],
            name="fk_dce_doc_issues__document",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_document_issues__tenant_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dce_document_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    issue_kind: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    impact: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    locator_json: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    created_by_actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class DceMissingDocumentDeclarationRecord(TenantScopedRecord, Base):
    __tablename__ = "dce_missing_document_declarations"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_missing_docs__version",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uq_dce_missing_document_declarations__tenant_id"
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    expected_document_family: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    expectation_source_kind: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    expectation_source_id: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    reason: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    created_by_actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class DceSourceStatementRecord(TenantScopedRecord, Base):
    __tablename__ = "dce_source_statements"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_source_statements__version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_document_id"],
            ["dce_documents.tenant_id", "dce_documents.id"],
            name="fk_dce_source_statements__document",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_source_statements__tenant_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dce_document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    locator_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    excerpt: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    source_language: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    extraction_origin: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    created_by_actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
