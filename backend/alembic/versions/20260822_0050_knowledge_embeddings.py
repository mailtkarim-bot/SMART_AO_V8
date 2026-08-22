"""Add immutable local retrieval embeddings for DCE fragments."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "20260822_0050"
down_revision = "20260822_0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dce_fragment_embeddings",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("dce_version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", UUID(as_uuid=True), nullable=False),
        sa.Column("fragment_id", UUID(as_uuid=True), nullable=False),
        sa.Column("model_id", sa.String(length=180), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("locator_json", JSONB, nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("text_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("embedding", JSONB, nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_dce_fragment_embeddings__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_fragment_embeddings__dce_versions__tenant_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_dce_fragment_embeddings__cases__tenant_case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "fragment_id"],
            ["dce_document_extraction_fragments.tenant_id", "dce_document_extraction_fragments.id"],
            name="fk_dce_fragment_embeddings__fragments__tenant_fragment",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dce_fragment_embeddings"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_fragment_embeddings__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "fragment_id",
            "model_id",
            name="uq_dce_fragment_embeddings__fragment_model",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(embedding) = 'array'",
            name="embedding_is_array",
        ),
        sa.CheckConstraint("ordinal > 0", name="ordinal_positive"),
        sa.CheckConstraint("char_length(text) > 0", name="text_nonempty"),
        sa.CheckConstraint(
            "classification IN ('PUBLIC', 'INTERNAL_OPERATIONAL')",
            name="classification_allowed",
        ),
        sa.CheckConstraint("embedding_dimension > 0", name="embedding_dimension_positive"),
        sa.CheckConstraint(
            "jsonb_array_length(embedding) = embedding_dimension",
            name="embedding_length",
        ),
    )
    op.create_index(
        "ix_dce_fragment_embeddings_tenant_id",
        "dce_fragment_embeddings",
        ["tenant_id"],
    )
    op.create_index(
        "ix_dce_fragment_embeddings__tenant_version_model",
        "dce_fragment_embeddings",
        ["tenant_id", "case_id", "dce_version_id", "model_id"],
    )
    op.create_index(
        "ix_dce_fragment_embeddings__tenant_fragment_model",
        "dce_fragment_embeddings",
        ["tenant_id", "fragment_id", "model_id"],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_dce_fragment_embedding_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'dce fragment embeddings are append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER dce_fragment_embeddings_append_only
        BEFORE UPDATE OR DELETE ON dce_fragment_embeddings
        FOR EACH ROW EXECUTE FUNCTION prevent_dce_fragment_embedding_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS dce_fragment_embeddings_append_only
        ON dce_fragment_embeddings
        """
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_dce_fragment_embedding_mutation()")
    op.execute(
        "DROP INDEX IF EXISTS ix_dce_fragment_embeddings__tenant_fragment_model"
    )
    op.execute("DROP INDEX IF EXISTS ix_dce_fragment_embeddings_tenant_id")
    op.execute(
        "DROP INDEX IF EXISTS ix_dce_fragment_embeddings__tenant_version_model"
    )
    op.drop_table("dce_fragment_embeddings")
