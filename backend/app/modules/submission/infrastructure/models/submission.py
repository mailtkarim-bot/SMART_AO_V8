from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from app.platform.persistence.base import Base, TenantScopedRecord
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


class SubmissionPackageRecord(TenantScopedRecord, Base):
    """Immutable patron-controlled package prepared for human submission."""

    __tablename__ = "submission_packages"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_submission_package__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "preparation_package_id"],
            ["preparation_packages.tenant_id", "preparation_packages.id"],
            name="fk_submission_package__preparation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "technical_document_id"],
            ["generated_technical_documents.tenant_id", "generated_technical_documents.id"],
            name="fk_submission_package__document",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "financial_snapshot_id"],
            ["financial_report_snapshots.tenant_id", "financial_report_snapshots.id"],
            name="fk_submission_package__financial_snapshot",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_submission_package__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "preparation_package_id",
            "version",
            name="uq_submission_package__preparation_version",
        ),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_submission_package__command"),
        sa.CheckConstraint("version > 0", name="version_positive"),
        sa.CheckConstraint(
            "state IN ('PRET_CONTROLE', 'AUTORISE_DEPOT')",
            name="state",
        ),
        sa.CheckConstraint("technical_document_version > 0", name="technical_document_version"),
        sa.CheckConstraint("financial_snapshot_revision >= 0", name="financial_snapshot_revision"),
        sa.Index(
            "ix_submission_packages__tenant_preparation_version",
            "tenant_id",
            "preparation_package_id",
            "version",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    preparation_package_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    technical_document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    technical_document_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    financial_snapshot_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    financial_snapshot_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    manifest_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

class SubmissionEvidenceRecord(TenantScopedRecord, Base):
    """Human-provided evidence; it never asserts automated external submission success."""

    __tablename__ = "submission_evidence"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "submission_package_id"],
            ["submission_packages.tenant_id", "submission_packages.id"],
            name="fk_submission_evidence__package",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_submission_evidence__tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_submission_evidence__command"),
        sa.CheckConstraint(
            "evidence_type IN ('MANUAL_RECEIPT', 'MANUAL_PORTAL_REFERENCE')", name="evidence_type"
        ),
        sa.CheckConstraint("status IN ('RECEIVED', 'REJECTED')", name="status"),
        sa.Index("ix_submission_evidence__tenant_package", "tenant_id", "submission_package_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    submission_package_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    evidence_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    external_reference_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    notes_redacted: Mapped[str | None] = mapped_column(sa.String(1000))
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class SubmissionSignatureRecord(TenantScopedRecord, Base):
    """Append-only electronic-signature intent and provider proof."""

    __tablename__ = "submission_signatures"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_submission_signatures__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "submission_package_id"],
            ["submission_packages.tenant_id", "submission_packages.id"],
            name="fk_submission_signatures__submission_packages__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_submission_signatures__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "command_id", name="uq_submission_signatures__tenant_command"
        ),
        sa.CheckConstraint(
            "status IN ('REQUESTED', 'SIGNED', 'REJECTED')", name="status"
        ),
        sa.CheckConstraint("expected_package_version > 0", name="expected_package_version"),
        sa.CheckConstraint(
            "provider_reference_hash IS NULL OR provider_reference_hash ~ '^[a-f0-9]{64}$'",
            name="provider_reference_hash",
        ),
        sa.CheckConstraint(
            "signature_sha256 IS NULL OR signature_sha256 ~ '^[a-f0-9]{64}$'",
            name="signature_sha256",
        ),
        sa.Index("ix_submission_signatures__tenant_package", "tenant_id", "submission_package_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    submission_package_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    signer_membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    expected_package_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    provider_reference_hash: Mapped[str | None] = mapped_column(sa.CHAR(64))
    signature_sha256: Mapped[str | None] = mapped_column(sa.CHAR(64))
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

