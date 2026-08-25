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

class EnterpriseCapabilityRecord(TenantScopedRecord, Base):
    """Patron-owned reusable capability root, separate from any Case assessment."""

    __tablename__ = "enterprise_capabilities"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_enterprise_capability__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "company_id"],
            ["enterprise_companies.tenant_id", "enterprise_companies.id"],
            name="fk_enterprise_capability__company",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_enterprise_capability__tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_enterprise_capability__command"),
        sa.UniqueConstraint(
            "tenant_id",
            "company_id",
            "capability_kind",
            "name",
            name="uq_enterprise_capability__identity",
        ),
        sa.Index(
            "ix_enterprise_capabilities__tenant_company_kind_state",
            "tenant_id",
            "company_id",
            "capability_kind",
            "state",
        ),
        sa.CheckConstraint(
            "capability_kind IN ('QUALIFICATION', 'REFERENCE', 'EQUIPMENT', 'TEAM', 'METHOD')",
            name="capability_kind",
        ),
        sa.CheckConstraint("state IN ('ACTIVE', 'SUSPENDED', 'RETIRED')", name="state"),
        sa.CheckConstraint("aggregate_revision >= 0", name="aggregate_revision"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    aggregate_revision: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )
    capability_kind: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    summary: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

class EnterpriseCapabilityVersionRecord(TenantScopedRecord, Base):
    """Immutable dated version of one enterprise capability."""

    __tablename__ = "enterprise_capability_versions"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "capability_id"],
            ["enterprise_capabilities.tenant_id", "enterprise_capabilities.id"],
            name="fk_enterprise_capability_version__capability",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_enterprise_capability_version__membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_enterprise_capability_version__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "command_id", name="uq_enterprise_capability_version__command"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "capability_id",
            "version_number",
            name="uq_enterprise_capability_version__number",
        ),
        sa.Index(
            "ix_enterprise_capability_versions__tenant_capability_validity",
            "tenant_id",
            "capability_id",
            "valid_until",
        ),
        sa.CheckConstraint("version_number > 0", name="version_number"),
        sa.CheckConstraint("valid_until IS NULL OR valid_until > valid_from", name="validity"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    capability_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    title: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    usage_scope: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    created_by_membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

class EnterpriseCapabilityProofLinkRecord(TenantScopedRecord, Base):
    """Immutable link from a capability version to an enterprise document proof."""

    __tablename__ = "enterprise_capability_proof_links"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "capability_version_id"],
            ["enterprise_capability_versions.tenant_id", "enterprise_capability_versions.id"],
            name="fk_enterprise_capability_proof_link__version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["enterprise_documents.tenant_id", "enterprise_documents.id"],
            name="fk_enterprise_capability_proof_link__document",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uq_enterprise_capability_proof_link__tenant_id"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "capability_version_id",
            "document_id",
            name="uq_enterprise_capability_proof_link__identity",
        ),
        sa.CheckConstraint("length(trim(relation_label)) > 0", name="relation_label"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    capability_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    relation_label: Mapped[str] = mapped_column(sa.String(240), nullable=False)

class CaseCapabilityProposalRecord(TenantScopedRecord, Base):
    """Collaborator candidate use of an enterprise capability for one Case."""

    __tablename__ = "case_capability_proposals"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_case_capability_proposal__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["case_assignments.tenant_id", "case_assignments.id"],
            name="fk_case_capability_proposal__assignment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "capability_id"],
            ["enterprise_capabilities.tenant_id", "enterprise_capabilities.id"],
            name="fk_case_capability_proposal__capability",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "capability_version_id"],
            ["enterprise_capability_versions.tenant_id", "enterprise_capability_versions.id"],
            name="fk_case_capability_proposal__version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "requirement_id"],
            ["dce_requirements.tenant_id", "dce_requirements.id"],
            name="fk_case_capability_proposal__requirement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["collaborator_tasks.tenant_id", "collaborator_tasks.id"],
            name="fk_case_capability_proposal__task",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "proposed_by_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_case_capability_proposal__membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_case_capability_proposal__tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_case_capability_proposal__command"),
        sa.UniqueConstraint(
            "tenant_id", "functional_key", name="uq_case_capability_proposal__functional"
        ),
        sa.CheckConstraint("state IN ('PROPOSED', 'TO_REVIEW')", name="state"),
        sa.CheckConstraint(
            "validity_state IN ('CURRENT', 'EXPIRED', 'UNKNOWN')", name="validity_state"
        ),
        sa.CheckConstraint(
            "requirement_id IS NOT NULL OR task_id IS NOT NULL", name="source_required"
        ),
        sa.Index(
            "ix_case_capability_proposals__tenant_case_state",
            "tenant_id",
            "case_id",
            "state",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    assignment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    capability_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    capability_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    requirement_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    task_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="PROPOSED")
    validity_state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    justification: Mapped[str] = mapped_column(sa.String(2000), nullable=False)
    source_locator: Mapped[str | None] = mapped_column(sa.String(500))
    functional_key: Mapped[str] = mapped_column(sa.String(700), nullable=False)
    proposed_by_membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

class CaseCapabilityGapRecord(TenantScopedRecord, Base):
    """Collaborator finding that a Case capability/proof is missing or unusable."""

    __tablename__ = "case_capability_gaps"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_case_capability_gap__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["case_assignments.tenant_id", "case_assignments.id"],
            name="fk_case_capability_gap__assignment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "capability_id"],
            ["enterprise_capabilities.tenant_id", "enterprise_capabilities.id"],
            name="fk_case_capability_gap__capability",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "requirement_id"],
            ["dce_requirements.tenant_id", "dce_requirements.id"],
            name="fk_case_capability_gap__requirement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["collaborator_tasks.tenant_id", "collaborator_tasks.id"],
            name="fk_case_capability_gap__task",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "reported_by_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_case_capability_gap__membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_case_capability_gap__tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_case_capability_gap__command"),
        sa.UniqueConstraint(
            "tenant_id", "functional_key", name="uq_case_capability_gap__functional"
        ),
        sa.CheckConstraint(
            "gap_kind IN ('MISSING', 'EXPIRED', 'UNAUTHORIZED', 'INSUFFICIENT')", name="gap_kind"
        ),
        sa.CheckConstraint(
            "severity IN ('INFORMATIONAL', 'IMPORTANT', 'BLOCKING')", name="severity"
        ),
        sa.CheckConstraint(
            "requirement_id IS NOT NULL OR task_id IS NOT NULL", name="source_required"
        ),
        sa.Index(
            "ix_case_capability_gaps__tenant_case_severity",
            "tenant_id",
            "case_id",
            "severity",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    assignment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    capability_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    requirement_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    task_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    gap_kind: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    severity: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    reason: Mapped[str] = mapped_column(sa.String(2000), nullable=False)
    source_locator: Mapped[str | None] = mapped_column(sa.String(500))
    recommended_action: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    functional_key: Mapped[str] = mapped_column(sa.String(700), nullable=False)
    reported_by_membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
