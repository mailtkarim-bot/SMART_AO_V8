"""Create Consultation and DceVersion persistence.

Revision ID: 20260813_0002
Revises: 20260813_0001
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260813_0002"
down_revision = "20260813_0001"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())
TIMESTAMPTZ = sa.DateTime(timezone=True)
NOW = sa.text("CURRENT_TIMESTAMP")


def _audit_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=NOW),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False, server_default=NOW),
    ]


def upgrade() -> None:
    op.create_table(
        "consultations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("aggregate_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("functional_identity_hash", sa.CHAR(64), nullable=False),
        sa.Column("buyer_legal_name", sa.String(240), nullable=False),
        sa.Column("buyer_normalized_id", sa.String(120), nullable=True),
        sa.Column("external_reference", sa.String(240), nullable=True),
        sa.Column("object_label", sa.String(240), nullable=False),
        sa.Column("location_label", sa.String(500), nullable=True),
        sa.Column("source_channel", sa.String(120), nullable=False),
        sa.Column("source_reference", sa.String(500), nullable=True),
        sa.Column("source_received_at", TIMESTAMPTZ, nullable=False),
        sa.Column("lifecycle", sa.String(32), nullable=False),
        sa.Column("freshness", sa.String(32), nullable=False),
        sa.Column(
            "metadata_history_json",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("created_by_actor_id", UUID, nullable=True),
        sa.Column("updated_by_actor_id", UUID, nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_consultations__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_consultations__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "functional_identity_hash",
            name="uq_consultations__tenant_functional_identity",
        ),
        sa.CheckConstraint(
            "lifecycle IN ('OPEN', 'CLOSED', 'ARCHIVED')",
            name="lifecycle",
        ),
        sa.CheckConstraint(
            "freshness IN ('UNKNOWN', 'CURRENT', 'REVIEW_REQUIRED')",
            name="freshness",
        ),
    )
    op.create_index("ix_consultations_tenant_id", "consultations", ["tenant_id"])
    op.create_index(
        "ux_consultations__tenant_buyer_reference",
        "consultations",
        ["tenant_id", "buyer_normalized_id", "external_reference"],
        unique=True,
        postgresql_where=sa.text(
            "buyer_normalized_id IS NOT NULL AND external_reference IS NOT NULL"
        ),
    )
    op.create_index(
        "ix_consultations__tenant_lifecycle_updated",
        "consultations",
        ["tenant_id", "lifecycle", sa.text("updated_at DESC")],
    )

    op.create_table(
        "consultation_lots",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("consultation_id", UUID, nullable=False),
        sa.Column("lot_number", sa.String(80), nullable=False),
        sa.Column("label", sa.String(240), nullable=False),
        sa.Column("source_reference", sa.String(500), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "consultation_id"],
            ["consultations.tenant_id", "consultations.id"],
            name="fk_consultation_lots__consultations__tenant_consultation_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_consultation_lots__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "consultation_id",
            "lot_number",
            name="uq_consultation_lots__tenant_consultation_lot_number",
        ),
    )
    op.create_index("ix_consultation_lots_tenant_id", "consultation_lots", ["tenant_id"])

    op.create_table(
        "consultation_tranches",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("consultation_id", UUID, nullable=False),
        sa.Column("tranche_reference", sa.String(120), nullable=False),
        sa.Column("tranche_kind", sa.String(120), nullable=False),
        sa.Column("label", sa.String(240), nullable=True),
        sa.Column("source_reference", sa.String(500), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "consultation_id"],
            ["consultations.tenant_id", "consultations.id"],
            name="fk_consultation_tranches__consultations__tenant_consultation_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_consultation_tranches__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "consultation_id",
            "tranche_reference",
            name="uq_consultation_tranches__tenant_consultation_tranche_reference",
        ),
        sa.CheckConstraint("length(trim(tranche_kind)) > 0", name="tranche_kind"),
    )
    op.create_index(
        "ix_consultation_tranches_tenant_id",
        "consultation_tranches",
        ["tenant_id"],
    )

    op.create_table(
        "dce_versions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("aggregate_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consultation_id", UUID, nullable=False),
        sa.Column("corpus_hash", sa.CHAR(64), nullable=False),
        sa.Column("predecessor_dce_version_id", UUID, nullable=True),
        sa.Column("provenance_channel", sa.String(120), nullable=False),
        sa.Column("provenance_reference", sa.String(500), nullable=True),
        sa.Column("provenance_url", sa.Text(), nullable=True),
        sa.Column("source_received_at", TIMESTAMPTZ, nullable=False),
        sa.Column("lifecycle", sa.String(32), nullable=False),
        sa.Column("integrity", sa.String(32), nullable=False),
        sa.Column("classification_readiness", sa.String(32), nullable=False),
        sa.Column("analysis_readiness", sa.String(32), nullable=False),
        sa.Column("withdrawal_source", sa.Text(), nullable=True),
        sa.Column("withdrawal_reason", sa.Text(), nullable=True),
        sa.Column("superseded_at", TIMESTAMPTZ, nullable=True),
        sa.Column("withdrawn_at", TIMESTAMPTZ, nullable=True),
        sa.Column("created_by_actor_id", UUID, nullable=True),
        sa.Column("updated_by_actor_id", UUID, nullable=True),
        *_audit_columns(),
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
    )
    op.create_index("ix_dce_versions_tenant_id", "dce_versions", ["tenant_id"])
    op.create_index(
        "ix_dce_versions__tenant_consultation_received",
        "dce_versions",
        ["tenant_id", "consultation_id", sa.text("source_received_at DESC")],
    )
    op.create_index(
        "ix_dce_versions__tenant_predecessor",
        "dce_versions",
        ["tenant_id", "predecessor_dce_version_id"],
    )

    op.create_table(
        "dce_documents",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("dce_version_id", UUID, nullable=False),
        sa.Column("storage_object_id", UUID, nullable=False),
        sa.Column("storage_key", sa.String(1000), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("media_type", sa.String(180), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.CHAR(64), nullable=False),
        sa.Column("received_from", sa.String(240), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_documents__dce_versions__tenant_dce_version_id",
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
    op.create_index("ix_dce_documents_tenant_id", "dce_documents", ["tenant_id"])

    op.create_table(
        "dce_document_classifications",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("dce_document_id", UUID, nullable=False),
        sa.Column("classification", sa.String(120), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("previous_classification_id", UUID, nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_actor_id", UUID, nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_document_id"],
            ["dce_documents.tenant_id", "dce_documents.id"],
            name="fk_dce_doc_class__document",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "previous_classification_id"],
            [
                "dce_document_classifications.tenant_id",
                "dce_document_classifications.id",
            ],
            name="fk_dce_doc_class__previous",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uq_dce_document_classifications__tenant_id"
        ),
    )
    op.create_index(
        "ix_dce_document_classifications_tenant_id",
        "dce_document_classifications",
        ["tenant_id"],
    )
    op.create_index(
        "ux_dce_document_classifications__current_document",
        "dce_document_classifications",
        ["tenant_id", "dce_document_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )

    op.create_table(
        "dce_document_issues",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("dce_version_id", UUID, nullable=False),
        sa.Column("dce_document_id", UUID, nullable=True),
        sa.Column("issue_kind", sa.String(120), nullable=False),
        sa.Column("impact", sa.String(32), nullable=False),
        sa.Column("locator_json", JSONB, nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_actor_id", UUID, nullable=True),
        *_audit_columns(),
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
    op.create_index(
        "ix_dce_document_issues_tenant_id",
        "dce_document_issues",
        ["tenant_id"],
    )

    op.create_table(
        "dce_missing_document_declarations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("dce_version_id", UUID, nullable=False),
        sa.Column("expected_document_family", sa.String(120), nullable=False),
        sa.Column("expectation_source_kind", sa.String(120), nullable=False),
        sa.Column("expectation_source_id", sa.String(240), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_actor_id", UUID, nullable=True),
        *_audit_columns(),
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
    op.create_index(
        "ix_dce_missing_document_declarations_tenant_id",
        "dce_missing_document_declarations",
        ["tenant_id"],
    )

    op.create_table(
        "dce_source_statements",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("dce_version_id", UUID, nullable=False),
        sa.Column("dce_document_id", UUID, nullable=False),
        sa.Column("locator_json", JSONB, nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("source_language", sa.String(32), nullable=True),
        sa.Column("extraction_origin", sa.String(120), nullable=False),
        sa.Column("created_by_actor_id", UUID, nullable=True),
        *_audit_columns(),
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
    op.create_index(
        "ix_dce_source_statements_tenant_id",
        "dce_source_statements",
        ["tenant_id"],
    )

    op.execute(
        """
        CREATE FUNCTION protect_admitted_dce_content() RETURNS trigger AS $$
        BEGIN
          IF OLD.corpus_hash IS DISTINCT FROM NEW.corpus_hash
             OR OLD.consultation_id IS DISTINCT FROM NEW.consultation_id THEN
            RAISE EXCEPTION 'DOCUMENT_ORIGINAL_IMMUTABLE';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_dce_versions_immutable_content
        BEFORE UPDATE ON dce_versions
        FOR EACH ROW EXECUTE FUNCTION protect_admitted_dce_content();
        """
    )
    op.execute(
        """
        CREATE FUNCTION protect_dce_document_original() RETURNS trigger AS $$
        BEGIN
          IF OLD.storage_object_id IS DISTINCT FROM NEW.storage_object_id
             OR OLD.storage_key IS DISTINCT FROM NEW.storage_key
             OR OLD.original_filename IS DISTINCT FROM NEW.original_filename
             OR OLD.media_type IS DISTINCT FROM NEW.media_type
             OR OLD.byte_size IS DISTINCT FROM NEW.byte_size
             OR OLD.sha256 IS DISTINCT FROM NEW.sha256 THEN
            RAISE EXCEPTION 'DOCUMENT_ORIGINAL_IMMUTABLE';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_dce_documents_immutable_content
        BEFORE UPDATE ON dce_documents
        FOR EACH ROW EXECUTE FUNCTION protect_dce_document_original();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_dce_documents_immutable_content ON dce_documents")
    op.execute("DROP FUNCTION IF EXISTS protect_dce_document_original()")
    op.execute("DROP TRIGGER IF EXISTS trg_dce_versions_immutable_content ON dce_versions")
    op.execute("DROP FUNCTION IF EXISTS protect_admitted_dce_content()")

    op.drop_index("ix_dce_source_statements_tenant_id", table_name="dce_source_statements")
    op.drop_table("dce_source_statements")
    op.drop_index(
        "ix_dce_missing_document_declarations_tenant_id",
        table_name="dce_missing_document_declarations",
    )
    op.drop_table("dce_missing_document_declarations")
    op.drop_index("ix_dce_document_issues_tenant_id", table_name="dce_document_issues")
    op.drop_table("dce_document_issues")
    op.drop_index(
        "ux_dce_document_classifications__current_document",
        table_name="dce_document_classifications",
    )
    op.drop_index(
        "ix_dce_document_classifications_tenant_id",
        table_name="dce_document_classifications",
    )
    op.drop_table("dce_document_classifications")
    op.drop_index("ix_dce_documents_tenant_id", table_name="dce_documents")
    op.drop_table("dce_documents")
    op.drop_index("ix_dce_versions__tenant_predecessor", table_name="dce_versions")
    op.drop_index(
        "ix_dce_versions__tenant_consultation_received",
        table_name="dce_versions",
    )
    op.drop_index("ix_dce_versions_tenant_id", table_name="dce_versions")
    op.drop_table("dce_versions")
    op.drop_index(
        "ix_consultation_tranches_tenant_id",
        table_name="consultation_tranches",
    )
    op.drop_table("consultation_tranches")
    op.drop_index("ix_consultation_lots_tenant_id", table_name="consultation_lots")
    op.drop_table("consultation_lots")
    op.drop_index(
        "ix_consultations__tenant_lifecycle_updated",
        table_name="consultations",
    )
    op.drop_index(
        "ux_consultations__tenant_buyer_reference",
        table_name="consultations",
    )
    op.drop_index("ix_consultations_tenant_id", table_name="consultations")
    op.drop_table("consultations")
