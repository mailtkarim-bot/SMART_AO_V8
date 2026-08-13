"""Create immutable DCE document extraction registry.

Revision ID: 20260813_0013
Revises: 20260813_0012
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260813_0013"
down_revision = "20260813_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dce_document_extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dce_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dce_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("input_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("extractor_id", sa.String(length=100), nullable=False),
        sa.Column("extractor_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("fragment_count", sa.Integer(), nullable=False),
        sa.Column("extracted_char_count", sa.Integer(), nullable=False),
        sa.Column("failure_code", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "fragment_count >= 0",
            name="fragment_count_nonnegative",
        ),
        sa.CheckConstraint(
            "extracted_char_count >= 0",
            name="char_count_nonnegative",
        ),
        sa.CheckConstraint(
            "(status = 'COMPLETED' AND failure_code IS NULL) OR "
            "(status <> 'COMPLETED' AND failure_code IS NOT NULL)",
            name="status_failure_code",
        ),
        sa.CheckConstraint(
            "status IN ('COMPLETED', 'UNSUPPORTED', 'REJECTED_LIMIT', 'FAILED_SAFE')",
            name="status",
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
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_dce_document_extractions__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dce_document_extractions"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_extract__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "dce_document_id",
            "input_sha256",
            "extractor_id",
            "extractor_version",
            name="uq_dce_extract__document_input_extractor",
        ),
    )
    op.create_index(
        "ix_dce_extract__tenant_document_created",
        "dce_document_extractions",
        ["tenant_id", "dce_document_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_dce_document_extractions_tenant_id",
        "dce_document_extractions",
        ["tenant_id"],
    )

    op.create_table(
        "dce_document_extraction_fragments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extraction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column(
            "locator_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "ordinal > 0",
            name="ordinal_positive",
        ),
        sa.CheckConstraint(
            "char_length(text) > 0",
            name="text_nonempty",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "extraction_id"],
            ["dce_document_extractions.tenant_id", "dce_document_extractions.id"],
            name="fk_dce_extract_frag__extraction",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_dce_document_extraction_fragments__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dce_document_extraction_fragments"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_extract_frag__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "extraction_id",
            "ordinal",
            name="uq_dce_extract_frag__ordinal",
        ),
    )
    op.create_index(
        "ix_dce_extract_frag__tenant_extraction",
        "dce_document_extraction_fragments",
        ["tenant_id", "extraction_id", "ordinal"],
        unique=False,
    )
    op.create_index(
        "ix_dce_document_extraction_fragments_tenant_id",
        "dce_document_extraction_fragments",
        ["tenant_id"],
    )

    op.execute(
        """
        CREATE FUNCTION prevent_dce_extraction_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'DCE_DOCUMENT_EXTRACTION_APPEND_ONLY';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_dce_extract_append_only
        BEFORE UPDATE OR DELETE ON dce_document_extractions
        FOR EACH ROW EXECUTE FUNCTION prevent_dce_extraction_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_dce_extract_frag_append_only
        BEFORE UPDATE OR DELETE ON dce_document_extraction_fragments
        FOR EACH ROW EXECUTE FUNCTION prevent_dce_extraction_mutation();
        """
    )
    op.execute(
        """
        CREATE FUNCTION validate_dce_extraction_fragment_parent()
        RETURNS trigger AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM dce_document_extractions extraction
                WHERE extraction.id = NEW.extraction_id
                  AND extraction.tenant_id = NEW.tenant_id
                  AND extraction.status = 'COMPLETED'
            ) THEN
                RAISE EXCEPTION 'DCE_DOCUMENT_EXTRACTION_FRAGMENT_PARENT_INVALID';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_dce_extract_frag_parent
        BEFORE INSERT ON dce_document_extraction_fragments
        FOR EACH ROW EXECUTE FUNCTION validate_dce_extraction_fragment_parent();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_dce_extract_frag_parent ON dce_document_extraction_fragments")
    op.execute("DROP FUNCTION validate_dce_extraction_fragment_parent()")
    op.execute(
        "DROP TRIGGER trg_dce_extract_frag_append_only "
        "ON dce_document_extraction_fragments"
    )
    op.execute("DROP TRIGGER trg_dce_extract_append_only ON dce_document_extractions")
    op.execute("DROP FUNCTION prevent_dce_extraction_mutation()")
    op.execute(
        "DROP INDEX IF EXISTS ix_dce_document_extraction_fragments_tenant_id"
    )
    op.execute(
        "DROP INDEX IF EXISTS ix_dce_document_extraction_fragments__tenant_id"
    )
    op.drop_index(
        "ix_dce_extract_frag__tenant_extraction",
        "dce_document_extraction_fragments",
    )
    op.drop_table("dce_document_extraction_fragments")
    op.execute("DROP INDEX IF EXISTS ix_dce_document_extractions_tenant_id")
    op.execute("DROP INDEX IF EXISTS ix_dce_document_extractions__tenant_id")
    op.drop_index(
        "ix_dce_extract__tenant_document_created",
        "dce_document_extractions",
    )
    op.drop_table("dce_document_extractions")
