"""Create immutable deterministic DCE document classification registry.

Revision ID: 20260814_0015
Revises: 20260814_0014
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260814_0015"
down_revision = "20260814_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "dce_document_classification_runs",
        sa.Column("id", uuid, nullable=False),
        sa.Column("tenant_id", uuid, nullable=False),
        sa.Column("dce_version_id", uuid, nullable=False),
        sa.Column("dce_version_revision_before", sa.Integer(), nullable=False),
        sa.Column("input_manifest_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("classifier_id", sa.String(length=100), nullable=False),
        sa.Column("classifier_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("document_count", sa.Integer(), nullable=False),
        sa.Column("source_fragment_count", sa.Integer(), nullable=False),
        sa.Column("source_char_count", sa.Integer(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_dce_document_classification_runs"),
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
    )
    op.create_index(
        "ix_dce_doc_class_runs__tenant_version_created",
        "dce_document_classification_runs",
        ["tenant_id", "dce_version_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_dce_document_classification_runs_tenant_id",
        "dce_document_classification_runs",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "dce_document_classification_results",
        sa.Column("id", uuid, nullable=False),
        sa.Column("tenant_id", uuid, nullable=False),
        sa.Column("classification_run_id", uuid, nullable=False),
        sa.Column("dce_version_id", uuid, nullable=False),
        sa.Column("dce_document_id", uuid, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=True),
        sa.Column("rule_match_count", sa.Integer(), nullable=False),
        sa.Column("classification_id", uuid, nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_dce_document_classification_results"),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uq_dce_document_classification_results__tenant_id"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "classification_run_id",
            "dce_document_id",
            name="uq_dce_doc_class_result_document",
        ),
    )
    op.create_index(
        "ix_dce_doc_class_results__tenant_run",
        "dce_document_classification_results",
        ["tenant_id", "classification_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_dce_document_classification_results_tenant_id",
        "dce_document_classification_results",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "dce_document_classification_evidence",
        sa.Column("id", uuid, nullable=False),
        sa.Column("tenant_id", uuid, nullable=False),
        sa.Column("classification_result_id", uuid, nullable=False),
        sa.Column("fragment_id", uuid, nullable=False),
        sa.Column("classification_id", uuid, nullable=False),
        sa.Column("rule_id", sa.String(length=120), nullable=False),
        sa.Column("rule_version", sa.String(length=64), nullable=False),
        sa.Column("start_byte_offset", sa.Integer(), nullable=False),
        sa.Column("end_byte_offset", sa.Integer(), nullable=False),
        sa.Column("excerpt", sa.String(length=1000), nullable=False),
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
        sa.CheckConstraint("start_byte_offset >= 0", name="start_offset_nonneg"),
        sa.CheckConstraint("end_byte_offset > start_byte_offset", name="offsets_ordered"),
        sa.CheckConstraint("char_length(excerpt) > 0", name="excerpt_nonempty"),
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
        sa.PrimaryKeyConstraint("id", name="pk_dce_document_classification_evidence"),
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
    )
    op.create_index(
        "ix_dce_doc_class_evidence__tenant_result",
        "dce_document_classification_evidence",
        ["tenant_id", "classification_result_id"],
        unique=False,
    )
    op.create_index(
        "ix_dce_document_classification_evidence_tenant_id",
        "dce_document_classification_evidence",
        ["tenant_id"],
        unique=False,
    )

    op.execute(
        """
        CREATE FUNCTION prevent_dce_document_classification_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'DCE_DOCUMENT_CLASSIFICATION_APPEND_ONLY';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table_name, trigger_name in (
        ("dce_document_classification_runs", "trg_dce_doc_class_runs_append_only"),
        ("dce_document_classification_results", "trg_dce_doc_class_results_append_only"),
        ("dce_document_classification_evidence", "trg_dce_doc_class_evidence_append_only"),
    ):
        op.execute(
            f"CREATE TRIGGER {trigger_name} BEFORE UPDATE OR DELETE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION prevent_dce_document_classification_mutation();"
        )

    op.execute(
        """
        CREATE FUNCTION validate_dce_document_classification_result_parent()
        RETURNS trigger AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM dce_document_classification_runs run
                JOIN dce_documents document
                  ON document.id = NEW.dce_document_id
                 AND document.tenant_id = NEW.tenant_id
                WHERE run.id = NEW.classification_run_id
                  AND run.tenant_id = NEW.tenant_id
                  AND run.dce_version_id = NEW.dce_version_id
                  AND document.dce_version_id = NEW.dce_version_id
                  AND run.status = 'COMPLETED'
            ) THEN
                RAISE EXCEPTION 'DCE_DOCUMENT_CLASSIFICATION_RESULT_PARENT_INVALID';
            END IF;
            IF NEW.status = 'CLASSIFIED' AND NOT EXISTS (
                SELECT 1
                FROM dce_document_classifications classification
                WHERE classification.id = NEW.classification_id
                  AND classification.tenant_id = NEW.tenant_id
                  AND classification.dce_document_id = NEW.dce_document_id
                  AND classification.classification = NEW.classification
            ) THEN
                RAISE EXCEPTION 'DCE_DOCUMENT_CLASSIFICATION_PROJECTION_INVALID';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_dce_doc_class_result_parent
        BEFORE INSERT ON dce_document_classification_results
        FOR EACH ROW EXECUTE FUNCTION validate_dce_document_classification_result_parent();
        """
    )
    op.execute(
        """
        CREATE FUNCTION validate_dce_document_classification_evidence_parent()
        RETURNS trigger AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM dce_document_classification_results result
                JOIN dce_document_classification_runs run
                  ON run.id = result.classification_run_id
                 AND run.tenant_id = result.tenant_id
                JOIN dce_document_extraction_fragments fragment
                  ON fragment.id = NEW.fragment_id
                 AND fragment.tenant_id = NEW.tenant_id
                JOIN dce_document_extractions extraction
                  ON extraction.id = fragment.extraction_id
                 AND extraction.tenant_id = fragment.tenant_id
                JOIN dce_document_classifications classification
                  ON classification.id = NEW.classification_id
                 AND classification.tenant_id = NEW.tenant_id
                WHERE result.id = NEW.classification_result_id
                  AND result.tenant_id = NEW.tenant_id
                  AND result.status = 'CLASSIFIED'
                  AND result.classification_id = NEW.classification_id
                  AND extraction.dce_document_id = result.dce_document_id
                  AND run.status = 'COMPLETED'
            ) THEN
                RAISE EXCEPTION 'DCE_DOCUMENT_CLASSIFICATION_EVIDENCE_PARENT_INVALID';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_dce_doc_class_evidence_parent
        BEFORE INSERT ON dce_document_classification_evidence
        FOR EACH ROW EXECUTE FUNCTION validate_dce_document_classification_evidence_parent();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER trg_dce_doc_class_evidence_parent "
        "ON dce_document_classification_evidence"
    )
    op.execute("DROP FUNCTION validate_dce_document_classification_evidence_parent()")
    op.execute(
        "DROP TRIGGER trg_dce_doc_class_result_parent "
        "ON dce_document_classification_results"
    )
    op.execute("DROP FUNCTION validate_dce_document_classification_result_parent()")
    op.execute(
        "DROP TRIGGER trg_dce_doc_class_evidence_append_only "
        "ON dce_document_classification_evidence"
    )
    op.execute(
        "DROP TRIGGER trg_dce_doc_class_results_append_only "
        "ON dce_document_classification_results"
    )
    op.execute(
        "DROP TRIGGER trg_dce_doc_class_runs_append_only "
        "ON dce_document_classification_runs"
    )
    op.execute("DROP FUNCTION prevent_dce_document_classification_mutation()")
    op.drop_index(
        "ix_dce_document_classification_evidence_tenant_id",
        "dce_document_classification_evidence",
    )
    op.drop_index(
        "ix_dce_doc_class_evidence__tenant_result",
        "dce_document_classification_evidence",
    )
    op.drop_table("dce_document_classification_evidence")
    op.drop_index(
        "ix_dce_document_classification_results_tenant_id",
        "dce_document_classification_results",
    )
    op.drop_index(
        "ix_dce_doc_class_results__tenant_run",
        "dce_document_classification_results",
    )
    op.drop_table("dce_document_classification_results")
    op.drop_index(
        "ix_dce_document_classification_runs_tenant_id",
        "dce_document_classification_runs",
    )
    op.drop_index(
        "ix_dce_doc_class_runs__tenant_version_created",
        "dce_document_classification_runs",
    )
    op.drop_table("dce_document_classification_runs")
