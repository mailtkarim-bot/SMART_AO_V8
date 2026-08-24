from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, TenantScopedRecord


class PreparationPackageRecord(TenantScopedRecord, Base):
    """Mutable preparation package owned by one case assignment and DCE version."""

    __tablename__ = "preparation_packages"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_prep_packages__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["case_assignments.tenant_id", "case_assignments.id"],
            name="fk_prep_packages__assignment",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_prep_packages__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "case_id",
            "assignment_id",
            "dce_version_id",
            name="uq_prep_package_identity",
        ),
        sa.CheckConstraint(
            "state IN ('IN_PREPARATION', 'A_REVIEW', 'READY', 'BLOCKED', 'GENERATED')", name="state"
        ),
        sa.CheckConstraint("aggregate_revision >= 0", name="aggregate_revision"),
        sa.Index("ix_prep_packages__tenant_case_state", "tenant_id", "case_id", "state"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    assignment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    state: Mapped[str] = mapped_column(
        sa.String(24), nullable=False, server_default="IN_PREPARATION"
    )
    aggregate_revision: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )
    created_by_actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

class PreparationReviewRecord(TenantScopedRecord, Base):
    """Immutable state transition for a versioned preparation target review."""

    __tablename__ = "preparation_reviews"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_preparation_review__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "package_id"],
            ["preparation_packages.tenant_id", "preparation_packages.id"],
            name="fk_preparation_review__package",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "target_document_id"],
            ["generated_technical_documents.tenant_id", "generated_technical_documents.id"],
            name="fk_preparation_review__document",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_preparation_review__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "review_id", "revision", name="uq_preparation_review__revision"
        ),
        sa.CheckConstraint(
            "state IN ('REQUESTED', 'ACCEPTED', 'RETURNED_WITH_CORRECTIONS', 'REJECTED')",
            name="state",
        ),
        sa.CheckConstraint("revision > 0", name="revision_positive"),
        sa.CheckConstraint("target_version > 0", name="target_version_positive"),
        sa.CheckConstraint(
            "decision_code IS NULL OR decision_code IN ("
            "'ACCEPTED', 'CORRECTIONS_REQUIRED', 'REJECTED'"
            ")",
            name="decision_code",
        ),
        sa.Index(
            "ix_preparation_reviews__tenant_target", "tenant_id", "target_document_id", "revision"
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    review_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    package_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    target_document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    target_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    state: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    decision_code: Mapped[str | None] = mapped_column(sa.String(32))
    decision_note: Mapped[str | None] = mapped_column(sa.String(2000))
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class PreparationReadinessRecord(TenantScopedRecord, Base):
    """Append-only deterministic completeness evaluation."""

    __tablename__ = "preparation_readiness"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_prep_readiness__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "package_id"],
            ["preparation_packages.tenant_id", "preparation_packages.id"],
            name="fk_prep_readiness__package",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_prep_readiness__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "package_id", "revision", name="uq_prep_readiness_revision"
        ),
        sa.CheckConstraint("revision > 0", name="revision_positive"),
        sa.CheckConstraint("state IN ('READY', 'READY_WITH_WARNINGS', 'BLOCKED')", name="state"),
        sa.CheckConstraint("checked_requirement_count >= 0", name="requirements_nonnegative"),
        sa.CheckConstraint("checked_task_count >= 0", name="tasks_nonnegative"),
        sa.Index(
            "ix_prep_readiness__tenant_package_revision", "tenant_id", "package_id", "revision"
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    package_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    blocker_codes_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    warning_codes_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    checked_requirement_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    checked_task_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    input_manifest_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    evaluator_id: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    evaluator_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

class GeneratedTechnicalDocumentRecord(TenantScopedRecord, Base):
    """Immutable generated technical document metadata; content stays private."""

    __tablename__ = "generated_technical_documents"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_generated_docs__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "package_id"],
            ["preparation_packages.tenant_id", "preparation_packages.id"],
            name="fk_generated_docs__package",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "readiness_id"],
            ["preparation_readiness.tenant_id", "preparation_readiness.id"],
            name="fk_generated_docs__readiness",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_generated_docs__tenant_id"),
        sa.UniqueConstraint("tenant_id", "package_id", "version", name="uq_generated_doc_version"),
        sa.CheckConstraint("version > 0", name="version_positive"),
        sa.CheckConstraint("document_kind IN ('TECHNICAL_RESPONSE')", name="document_kind"),
        sa.CheckConstraint("state IN ('GENERATED', 'FAILED_SAFE')", name="state"),
        sa.Index("ix_generated_docs__tenant_package_version", "tenant_id", "package_id", "version"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    package_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    readiness_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    document_kind: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    content_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(sa.String(700), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

class PreparationSnapshotRecord(TenantScopedRecord, Base):
    """Immutable non-financial preparation facts frozen for patron review."""

    __tablename__ = "preparation_snapshots"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_prep_snapshots__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "package_id"],
            ["preparation_packages.tenant_id", "preparation_packages.id"],
            name="fk_prep_snapshots__package",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "readiness_id"],
            ["preparation_readiness.tenant_id", "preparation_readiness.id"],
            name="fk_prep_snapshots__readiness",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "technical_document_id"],
            ["generated_technical_documents.tenant_id", "generated_technical_documents.id"],
            name="fk_prep_snapshots__document",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_prep_snapshots__tenant_id"),
        sa.UniqueConstraint("tenant_id", "package_id", "version", name="uq_prep_snapshot__version"),
        sa.CheckConstraint("version > 0", name="version_positive"),
        sa.CheckConstraint("state IN ('READY_FOR_PATRON_REVIEW')", name="state"),
        sa.Index("ix_prep_snapshots__tenant_package_version", "tenant_id", "package_id", "version"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    package_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    readiness_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    technical_document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    technical_document_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    state: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    manifest_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

class PreparationTransmissionRecord(TenantScopedRecord, Base):
    """Append-only handoff of one immutable preparation snapshot to the patron."""

    __tablename__ = "preparation_transmissions"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_prep_transmissions__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "package_id"],
            ["preparation_packages.tenant_id", "preparation_packages.id"],
            name="fk_prep_transmissions__package",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "snapshot_id"],
            ["preparation_snapshots.tenant_id", "preparation_snapshots.id"],
            name="fk_prep_transmissions__snapshot",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_prep_transmissions__tenant_id"),
        sa.UniqueConstraint("tenant_id", "snapshot_id", name="uq_prep_transmission__snapshot"),
        sa.CheckConstraint("state IN ('TRANSMITTED_TO_PATRON')", name="state"),
        sa.Index("ix_prep_transmissions__tenant_package", "tenant_id", "package_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    package_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    snapshot_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

class PreparationReviewCorrectionRecord(TenantScopedRecord, Base):
    """Immutable targeted correction attached to a review transition."""

    __tablename__ = "preparation_review_corrections"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_preparation_correction__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "review_id", "review_revision"],
            [
                "preparation_reviews.tenant_id",
                "preparation_reviews.review_id",
                "preparation_reviews.revision",
            ],
            name="fk_preparation_correction__review",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "target_document_id"],
            ["generated_technical_documents.tenant_id", "generated_technical_documents.id"],
            name="fk_preparation_correction__document",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_preparation_correction__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "review_id", "revision", name="uq_preparation_correction__revision"
        ),
        sa.CheckConstraint("revision > 0", name="revision_positive"),
        sa.CheckConstraint("review_revision > 0", name="review_revision_positive"),
        sa.CheckConstraint(
            "correction_code IN ("
            "'SOURCE_MISSING', 'SOURCE_WRONG', 'SECTION_INCOMPLETE', "
            "'WORDING_UNCLEAR'"
            ")",
            name="correction_code",
        ),
        sa.Index("ix_preparation_corrections__tenant_review", "tenant_id", "review_id", "revision"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    review_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    review_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    target_document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    correction_code: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    instruction: Mapped[str] = mapped_column(sa.String(2000), nullable=False)
    source_locator: Mapped[str | None] = mapped_column(sa.String(500))
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

class TechnicalResponseDraftRecord(TenantScopedRecord, Base):
    """Immutable, non-financial, versioned response draft metadata."""

    __tablename__ = "technical_response_drafts"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_technical_draft__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "package_id"],
            ["preparation_packages.tenant_id", "preparation_packages.id"],
            name="fk_technical_draft__package",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "source_document_id"],
            ["generated_technical_documents.tenant_id", "generated_technical_documents.id"],
            name="fk_technical_draft__document",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_technical_draft__tenant_id"),
        sa.UniqueConstraint("tenant_id", "draft_id", "version", name="uq_technical_draft__version"),
        sa.CheckConstraint("version > 0", name="version_positive"),
        sa.CheckConstraint(
            "state IN ("
            "'DRAFT', 'SUBMITTED_FOR_REVIEW', 'RETURNED_WITH_CORRECTIONS', "
            "'ACCEPTED_CANDIDATE'"
            ")",
            name="state",
        ),
        sa.CheckConstraint(
            "responsible_role IN ('COLLABORATEUR', 'PATRON_REVIEWER')",
            name="responsible_role",
        ),
        sa.Index("ix_technical_drafts__tenant_package", "tenant_id", "package_id", "version"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    draft_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    package_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source_document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    state: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    section_codes_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    source_refs_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    responsible_role: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    content_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(sa.String(700), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

