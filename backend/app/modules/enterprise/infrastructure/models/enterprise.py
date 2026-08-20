"""SQLAlchemy persistence records owned by the enterprise bounded context."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from app.platform.persistence.base import Base, TenantScopedRecord
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


class EnterpriseCompanyRecord(TenantScopedRecord, Base):
    """One patron-owned legal company profile per tenant."""

    __tablename__ = "enterprise_companies"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_enterprise_company__tenant", ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_enterprise_company__tenant_id"),
        sa.UniqueConstraint("tenant_id", name="uq_enterprise_company__tenant"),
        sa.UniqueConstraint("tenant_id", "siren", name="uq_enterprise_company__tenant_siren"),
        sa.UniqueConstraint("tenant_id", "siret", name="uq_enterprise_company__tenant_siret"),
        sa.CheckConstraint("siren ~ '^[0-9]{9}$'", name="siren"),
        sa.CheckConstraint("siret ~ '^[0-9]{14}$'", name="siret"),
        sa.CheckConstraint("vat_number ~ '^[A-Z]{2}[A-Z0-9]{2,30}$'", name="vat_number"),
        sa.CheckConstraint("country_code ~ '^[A-Z]{2}$'", name="country_code"),
        sa.CheckConstraint("aggregate_revision >= 0", name="aggregate_revision"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    aggregate_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    legal_name: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(sa.String(240))
    siren: Mapped[str] = mapped_column(sa.CHAR(9), nullable=False)
    siret: Mapped[str] = mapped_column(sa.CHAR(14), nullable=False)
    vat_number: Mapped[str] = mapped_column(sa.String(34), nullable=False)
    address_line1: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    postal_code: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    city: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    country_code: Mapped[str] = mapped_column(sa.CHAR(2), nullable=False)


class EnterpriseDocumentRecord(TenantScopedRecord, Base):
    """Immutable enterprise proof, insurance certificate or bank document."""

    __tablename__ = "enterprise_documents"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_enterprise_document__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "company_id"],
            ["enterprise_companies.tenant_id", "enterprise_companies.id"],
            name="fk_enterprise_document__company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "registered_by_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_enterprise_document__membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_enterprise_document__tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_enterprise_document__command"),
        sa.CheckConstraint("document_kind IN ('INSURANCE', 'KBIS', 'RIB')", name="document_kind"),
        sa.CheckConstraint(
            "verification_status IN ('PENDING', 'VALIDATED', 'EXPIRED', 'REJECTED')",
            name="verification_status",
        ),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
        sa.CheckConstraint("expires_at IS NULL OR expires_at > issued_at", name="expiry"),
        sa.CheckConstraint(
            "(document_kind = 'RIB' AND expires_at IS NULL) OR document_kind <> 'RIB'",
            name="rib_expiry",
        ),
        sa.Index(
            "ix_enterprise_document__tenant_company_kind_expiry",
            "tenant_id",
            "company_id",
            "document_kind",
            "expires_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    document_kind: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    document_label: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    storage_object_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    original_filename: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    verification_status: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    registered_by_membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class EnterpriseDocumentUploadRecord(TenantScopedRecord, Base):
    """Private upload ledger; storage_key and scan metadata never form a public projection."""

    __tablename__ = "enterprise_document_uploads"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_enterprise_upload__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "company_id"],
            ["enterprise_companies.tenant_id", "enterprise_companies.id"],
            name="fk_enterprise_upload__company",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_enterprise_upload__tenant_id"),
        sa.UniqueConstraint("storage_key", name="uq_enterprise_upload__storage_key"),
        sa.UniqueConstraint("tenant_id", "document_id", name="uq_enterprise_upload__document"),
        sa.CheckConstraint("document_kind IN ('INSURANCE', 'KBIS', 'RIB')", name="document_kind"),
        sa.CheckConstraint(
            "state IN ('AWAITING_UPLOAD', 'UPLOADING', 'QUARANTINED', 'CLEAN', "
            "'REJECTED', 'EXPIRED')",
            name="state",
        ),
        sa.CheckConstraint("expected_byte_size > 0", name="expected_byte_size_positive"),
        sa.CheckConstraint(
            "actual_byte_size IS NULL OR actual_byte_size > 0", name="actual_byte_size_positive"
        ),
        sa.CheckConstraint("sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'", name="sha256_lowercase"),
        sa.CheckConstraint(
            "scan_verdict IS NULL OR scan_verdict IN ('CLEAN', 'INFECTED', 'ERROR')",
            name="scan_verdict",
        ),
        sa.CheckConstraint(
            "state <> 'CLEAN' OR (actual_byte_size IS NOT NULL AND sha256 IS NOT NULL "
            "AND media_type IS NOT NULL AND scan_verdict = 'CLEAN' AND scanned_at IS NOT NULL)",
            name="clean_metadata_required",
        ),
        sa.Index("ix_enterprise_upload__tenant_company_state", "tenant_id", "company_id", "state"),
        sa.Index("ix_enterprise_upload__tenant_expiry", "tenant_id", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    document_kind: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    document_label: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    original_filename: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    storage_key: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    expected_byte_size: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    actual_byte_size: Mapped[int | None] = mapped_column(sa.BigInteger)
    sha256: Mapped[str | None] = mapped_column(sa.CHAR(64))
    media_type: Mapped[str | None] = mapped_column(sa.String(180))
    state: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    scan_verdict: Mapped[str | None] = mapped_column(sa.String(32))
    scanner_name: Mapped[str | None] = mapped_column(sa.String(120))
    scanner_signature_version: Mapped[str | None] = mapped_column(sa.String(240))
    scanned_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    rejection_code: Mapped[str | None] = mapped_column(sa.String(120))
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    created_by_membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class EnterpriseDocumentVerificationRecord(TenantScopedRecord, Base):
    """Append-only human decision history for one enterprise document."""

    __tablename__ = "enterprise_document_verifications"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_enterprise_verification__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["enterprise_documents.tenant_id", "enterprise_documents.id"],
            name="fk_enterprise_verification__document",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_enterprise_verification__membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_enterprise_verification__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "document_id", "revision", name="uq_enterprise_verification__revision"
        ),
        sa.CheckConstraint("revision >= 0", name="revision_nonnegative"),
        sa.CheckConstraint("outcome IN ('VALIDATED', 'REJECTED')", name="outcome"),
        sa.CheckConstraint(
            "reason_code IN ('DOCUMENT_ACCEPTED', 'DOCUMENT_ILLEGIBLE', 'DOCUMENT_EXPIRED', "
            "'DOCUMENT_MISMATCH', 'DOCUMENT_DUPLICATE')",
            name="reason_code",
        ),
        sa.Index(
            "ix_enterprise_verification__tenant_document",
            "tenant_id",
            "document_id",
            "revision",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    reason_code: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
