"""Immutable deterministic DCE document classification records and evidence."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, TenantScopedRecord


class DceDocumentClassificationRunRecord(TenantScopedRecord, Base):
    """One terminal deterministic classification run over a canonical DCE manifest."""

    __tablename__ = "dce_document_classification_runs"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_dce_doc_class_runs__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_doc_class_runs__version",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uq_dce_document_classification_runs__tenant_id"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "dce_version_id",
            "input_manifest_sha256",
            "classifier_id",
            "classifier_version",
            name="uq_dce_doc_class_run_identity",
        ),
        sa.CheckConstraint(
            "status IN ('COMPLETED', 'REJECTED_LIMIT', 'FAILED_SAFE')",
            name="status",
        ),
        sa.CheckConstraint("document_count > 0", name="document_count_positive"),
        sa.CheckConstraint(
            "dce_version_revision_before >= 0",
            name="dce_revision_nonneg",
        ),
        sa.CheckConstraint("source_fragment_count >= 0", name="source_fragments_nonneg"),
        sa.CheckConstraint("source_char_count >= 0", name="source_chars_nonneg"),
        sa.CheckConstraint(
            "(status = 'COMPLETED' AND failure_code IS NULL) OR "
            "(status <> 'COMPLETED' AND failure_code IS NOT NULL)",
            name="status_failure_code",
        ),
        sa.Index(
            "ix_dce_doc_class_runs__tenant_version_created",
            "tenant_id",
            "dce_version_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dce_version_revision_before: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    input_manifest_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    classifier_id: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    classifier_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    document_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    source_fragment_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    source_char_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    failure_code: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class DceDocumentClassificationResultRecord(TenantScopedRecord, Base):
    """One immutable classification result for one admitted document in a run."""

    __tablename__ = "dce_document_classification_results"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_dce_doc_class_results__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "classification_run_id"],
            ["dce_document_classification_runs.tenant_id", "dce_document_classification_runs.id"],
            name="fk_dce_doc_class_results__run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_doc_class_results__version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_document_id"],
            ["dce_documents.tenant_id", "dce_documents.id"],
            name="fk_dce_doc_class_results__document",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "classification_id"],
            ["dce_document_classifications.tenant_id", "dce_document_classifications.id"],
            name="fk_dce_doc_class_results__classification",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uq_dce_document_classification_results__tenant_id"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "classification_run_id",
            "dce_document_id",
            name="uq_dce_doc_class_result_document",
        ),
        sa.CheckConstraint(
            "status IN ('CLASSIFIED', 'UNCLASSIFIED', 'REVIEW_REQUIRED', 'NOT_EXTRACTED')",
            name="status",
        ),
        sa.CheckConstraint(
            "classification IS NULL OR classification IN ("
            "'RC', 'CCAP', 'AE', 'CCTP', 'DPGF', 'BPU', 'PLAN', 'ANNEX', "
            "'RECTIFICATION', 'OTHER'"
            ")",
            name="classification",
        ),
        sa.CheckConstraint("rule_match_count >= 0", name="rule_matches_nonneg"),
        sa.CheckConstraint(
            "(status = 'CLASSIFIED' AND classification IS NOT NULL "
            "AND classification_id IS NOT NULL AND rule_match_count > 0) OR "
            "(status <> 'CLASSIFIED' AND classification IS NULL "
            "AND classification_id IS NULL AND rule_match_count = 0)",
            name="status_classification",
        ),
        sa.Index("ix_dce_doc_class_results__tenant_run", "tenant_id", "classification_run_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    classification_run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dce_document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    classification: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    rule_match_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    classification_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class DceDocumentClassificationEvidenceRecord(TenantScopedRecord, Base):
    """One immutable fragment proof for a classified document result."""

    __tablename__ = "dce_document_classification_evidence"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_dce_doc_class_evidence__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "classification_result_id"],
            [
                "dce_document_classification_results.tenant_id",
                "dce_document_classification_results.id",
            ],
            name="fk_dce_doc_class_evidence__result",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "fragment_id"],
            ["dce_document_extraction_fragments.tenant_id", "dce_document_extraction_fragments.id"],
            name="fk_dce_doc_class_evidence__fragment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "classification_id"],
            ["dce_document_classifications.tenant_id", "dce_document_classifications.id"],
            name="fk_dce_doc_class_evidence__classification",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uq_dce_document_classification_evidence__tenant_id"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "classification_result_id",
            "fragment_id",
            "rule_id",
            "start_byte_offset",
            "end_byte_offset",
            name="uq_dce_doc_class_evidence_identity",
        ),
        sa.CheckConstraint("start_byte_offset >= 0", name="start_offset_nonneg"),
        sa.CheckConstraint("end_byte_offset > start_byte_offset", name="offsets_ordered"),
        sa.CheckConstraint("char_length(excerpt) > 0", name="excerpt_nonempty"),
        sa.Index(
            "ix_dce_doc_class_evidence__tenant_result",
            "tenant_id",
            "classification_result_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    classification_result_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    fragment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    classification_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    rule_id: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    rule_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    start_byte_offset: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    end_byte_offset: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    excerpt: Mapped[str] = mapped_column(sa.String(1_000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
