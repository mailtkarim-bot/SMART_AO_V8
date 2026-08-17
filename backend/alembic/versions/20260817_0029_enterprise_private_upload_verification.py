"""Enterprise private upload and human verification.

Revision ID: 20260817_0029
Revises: 20260817_0028
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260817_0029"
down_revision = "20260817_0028"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "enterprise_document_uploads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_kind", sa.String(16), nullable=False),
        sa.Column("document_label", sa.String(240), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("storage_key", sa.String(1000), nullable=False),
        sa.Column("expected_byte_size", sa.BigInteger(), nullable=False),
        sa.Column("actual_byte_size", sa.BigInteger()),
        sa.Column("sha256", sa.CHAR(64)),
        sa.Column("media_type", sa.String(180)),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("scan_verdict", sa.String(32)),
        sa.Column("scanner_name", sa.String(120)),
        sa.Column("scanner_signature_version", sa.String(240)),
        sa.Column("scanned_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_code", sa.String(120)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True)),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_enterprise_upload__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "company_id"],
            ["enterprise_companies.tenant_id", "enterprise_companies.id"],
            name="fk_enterprise_upload__company",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_enterprise_document_uploads"),
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
    )
    op.create_index(
        "ix_enterprise_document_uploads_tenant_id", "enterprise_document_uploads", ["tenant_id"]
    )
    op.create_index(
        "ix_enterprise_upload__tenant_company_state",
        "enterprise_document_uploads",
        ["tenant_id", "company_id", "state"],
    )
    op.create_index(
        "ix_enterprise_upload__tenant_expiry",
        "enterprise_document_uploads",
        ["tenant_id", "expires_at"],
    )

    op.create_table(
        "enterprise_document_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("reason_code", sa.String(40), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True)),
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
        sa.PrimaryKeyConstraint("id", name="pk_enterprise_document_verifications"),
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
    )
    op.create_index(
        "ix_enterprise_document_verifications_tenant_id",
        "enterprise_document_verifications",
        ["tenant_id"],
    )
    op.create_index(
        "ix_enterprise_verification__tenant_document",
        "enterprise_document_verifications",
        ["tenant_id", "document_id", "revision"],
    )
    op.execute("""
        CREATE FUNCTION prevent_enterprise_verification_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'enterprise document verifications are append-only'; END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER enterprise_verifications_append_only
        BEFORE UPDATE OR DELETE ON enterprise_document_verifications
        FOR EACH ROW EXECUTE FUNCTION prevent_enterprise_verification_mutation();
    """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS enterprise_verifications_append_only "
        "ON enterprise_document_verifications"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_enterprise_verification_mutation()")
    op.drop_index(
        "ix_enterprise_verification__tenant_document",
        table_name="enterprise_document_verifications",
    )
    op.execute("DROP INDEX IF EXISTS ix_enterprise_document_verifications_tenant_id")
    op.drop_table("enterprise_document_verifications")
    op.drop_index("ix_enterprise_upload__tenant_expiry", table_name="enterprise_document_uploads")
    op.drop_index(
        "ix_enterprise_upload__tenant_company_state", table_name="enterprise_document_uploads"
    )
    op.execute("DROP INDEX IF EXISTS ix_enterprise_document_uploads_tenant_id")
    op.execute("DROP INDEX IF EXISTS ix_enterprise_uploads_tenant_id")
    op.drop_table("enterprise_document_uploads")
