"""Allow human-review-required DCE OCR projections.

Revision ID: 20260826_0067
Revises: 20260826_0066
Create Date: 2026-08-26
"""

from collections.abc import Sequence

from alembic import op

revision = "20260826_0067"
down_revision = "20260826_0066"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_OLD_STATUS_CONSTRAINT = "status IN ('COMPLETED', 'UNSUPPORTED', 'REJECTED_LIMIT', 'FAILED_SAFE')"
_NEW_STATUS_CONSTRAINT = (
    "status IN ('COMPLETED', 'REVIEW_REQUIRED', 'UNSUPPORTED', 'REJECTED_LIMIT', 'FAILED_SAFE')"
)


def upgrade() -> None:
    op.drop_constraint("status", "dce_document_extractions", type_="check")
    op.create_check_constraint("status", "dce_document_extractions", _NEW_STATUS_CONSTRAINT)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_dce_extraction_fragment_parent()
        RETURNS trigger AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM dce_document_extractions extraction
                WHERE extraction.id = NEW.extraction_id
                  AND extraction.tenant_id = NEW.tenant_id
                  AND extraction.status IN ('COMPLETED', 'REVIEW_REQUIRED')
            ) THEN
                RAISE EXCEPTION 'DCE_DOCUMENT_EXTRACTION_FRAGMENT_PARENT_INVALID';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    op.execute(
        "UPDATE dce_document_extractions "
        "SET status = 'FAILED_SAFE', failure_code = 'OCR_REVIEW_STATUS_REMOVED' "
        "WHERE status = 'REVIEW_REQUIRED'"
    )
    op.drop_constraint("status", "dce_document_extractions", type_="check")
    op.create_check_constraint("status", "dce_document_extractions", _OLD_STATUS_CONSTRAINT)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_dce_extraction_fragment_parent()
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
