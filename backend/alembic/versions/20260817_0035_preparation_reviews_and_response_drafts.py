"""Create versioned preparation reviews, corrections and response drafts.

Revision ID: 20260817_0035
Revises: 20260817_0034
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260817_0035"
down_revision = "20260817_0034"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _append_only(table: str, function: str, trigger: str, message: str) -> None:
    op.execute(
        f"""
        CREATE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '{message}';
        END;
        $$;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {trigger}
        BEFORE UPDATE OR DELETE ON {table}
        FOR EACH ROW EXECUTE FUNCTION {function}();
        """
    )


def _drop_append_only(table: str, function: str, trigger: str) -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
    op.execute(f"DROP FUNCTION IF EXISTS {function}()")


def upgrade() -> None:
    review_fks = (
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
    )
    op.create_table(
        "preparation_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("package_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_version", sa.Integer, nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("decision_code", sa.String(length=32), nullable=True),
        sa.Column("decision_note", sa.String(length=2000), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        *review_fks,
        sa.PrimaryKeyConstraint("id", name="pk_preparation_reviews"),
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
            "'ACCEPTED', 'CORRECTIONS_REQUIRED', 'REJECTED')",
            name="decision_code",
        ),
    )
    op.create_index("ix_preparation_reviews_tenant_id", "preparation_reviews", ["tenant_id"])
    op.create_index(
        "ix_preparation_reviews__tenant_target",
        "preparation_reviews",
        ["tenant_id", "target_document_id", "revision"],
    )

    correction_fks = (
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
    )
    op.create_table(
        "preparation_review_corrections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_revision", sa.Integer, nullable=False),
        sa.Column("target_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("correction_code", sa.String(length=32), nullable=False),
        sa.Column("instruction", sa.String(length=2000), nullable=False),
        sa.Column("source_locator", sa.String(length=500), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        *correction_fks,
        sa.PrimaryKeyConstraint("id", name="pk_preparation_review_corrections"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_preparation_correction__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "review_id", "revision", name="uq_preparation_correction__revision"
        ),
        sa.CheckConstraint("revision > 0", name="revision_positive"),
        sa.CheckConstraint("review_revision > 0", name="review_revision_positive"),
        sa.CheckConstraint(
            "correction_code IN ("
            "'SOURCE_MISSING', 'SOURCE_WRONG', 'SECTION_INCOMPLETE', 'WORDING_UNCLEAR')",
            name="correction_code",
        ),
    )
    op.create_index(
        "ix_preparation_review_corrections_tenant_id",
        "preparation_review_corrections",
        ["tenant_id"],
    )
    op.create_index(
        "ix_preparation_corrections__tenant_review",
        "preparation_review_corrections",
        ["tenant_id", "review_id", "revision"],
    )

    draft_fks = (
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
    )
    op.create_table(
        "technical_response_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("package_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("section_codes_json", postgresql.JSONB, nullable=False),
        sa.Column("source_refs_json", postgresql.JSONB, nullable=False),
        sa.Column("responsible_role", sa.String(length=32), nullable=False),
        sa.Column("content_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=700), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        *draft_fks,
        sa.PrimaryKeyConstraint("id", name="pk_technical_response_drafts"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_technical_draft__tenant_id"),
        sa.UniqueConstraint("tenant_id", "draft_id", "version", name="uq_technical_draft__version"),
        sa.CheckConstraint("version > 0", name="version_positive"),
        sa.CheckConstraint(
            "state IN ("
            "'DRAFT', 'SUBMITTED_FOR_REVIEW', 'RETURNED_WITH_CORRECTIONS', 'ACCEPTED_CANDIDATE')",
            name="state",
        ),
        sa.CheckConstraint(
            "responsible_role IN ('COLLABORATEUR', 'PATRON_REVIEWER')", name="responsible_role"
        ),
    )
    op.create_index(
        "ix_technical_response_drafts_tenant_id",
        "technical_response_drafts",
        ["tenant_id"],
    )
    op.create_index(
        "ix_technical_drafts__tenant_package",
        "technical_response_drafts",
        ["tenant_id", "package_id", "version"],
    )

    _append_only(
        "preparation_reviews",
        "prevent_preparation_review_mutation",
        "preparation_reviews_append_only",
        "preparation reviews are append-only",
    )
    _append_only(
        "preparation_review_corrections",
        "prevent_preparation_correction_mutation",
        "preparation_review_corrections_append_only",
        "preparation review corrections are append-only",
    )
    _append_only(
        "technical_response_drafts",
        "prevent_technical_draft_mutation",
        "technical_response_drafts_append_only",
        "technical response drafts are append-only",
    )


def downgrade() -> None:
    _drop_append_only(
        "technical_response_drafts",
        "prevent_technical_draft_mutation",
        "technical_response_drafts_append_only",
    )
    _drop_append_only(
        "preparation_review_corrections",
        "prevent_preparation_correction_mutation",
        "preparation_review_corrections_append_only",
    )
    _drop_append_only(
        "preparation_reviews",
        "prevent_preparation_review_mutation",
        "preparation_reviews_append_only",
    )
    op.execute("DROP INDEX IF EXISTS ix_technical_drafts__tenant_package")
    op.execute("DROP INDEX IF EXISTS ix_technical_response_drafts_tenant_id")
    op.drop_table("technical_response_drafts")
    op.execute("DROP INDEX IF EXISTS ix_preparation_corrections__tenant_review")
    op.execute("DROP INDEX IF EXISTS ix_preparation_review_corrections_tenant_id")
    op.drop_table("preparation_review_corrections")
    op.execute("DROP INDEX IF EXISTS ix_preparation_reviews__tenant_target")
    op.execute("DROP INDEX IF EXISTS ix_preparation_reviews_tenant_id")
    op.drop_table("preparation_reviews")
