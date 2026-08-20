"""Create immutable normalized pricing import batches and rows.

Revision ID: 20260818_0043
Revises: 20260818_0042
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260818_0043"
down_revision = "20260818_0042"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pricing_import_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_kind", sa.String(length=16), nullable=False),
        sa.Column("source_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("aggregate_revision", sa.Integer, server_default="1", nullable=False),
        sa.Column("row_count", sa.Integer, nullable=False),
        sa.Column("valid_row_count", sa.Integer, nullable=False),
        sa.Column("error_count", sa.Integer, nullable=False),
        sa.Column("total_minor", sa.BigInteger, nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_pricing_import_batches"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_pricing_import_batches__tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_pricing_import_batches__tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_pricing_import_batches__command"),
        sa.CheckConstraint("document_kind IN ('DPGF', 'BPU', 'EXCEL')", name="document_kind"),
        sa.CheckConstraint("state IN ('PREVIEWED', 'COMMITTED')", name="state"),
        sa.CheckConstraint("aggregate_revision > 0", name="aggregate_revision_positive"),
        sa.CheckConstraint("row_count >= 0", name="row_count_non_negative"),
        sa.CheckConstraint(
            "valid_row_count >= 0 AND valid_row_count <= row_count", name="valid_rows_bound"
        ),
        sa.CheckConstraint("error_count >= 0", name="error_count_non_negative"),
        sa.CheckConstraint("total_minor >= 0", name="total_minor_non_negative"),
        sa.CheckConstraint("source_sha256 ~ '^[a-f0-9]{64}$'", name="source_sha256"),
    )
    op.create_index(
        "ix_pricing_import_batches_tenant_id", "pricing_import_batches", ["tenant_id"]
    )
    op.create_index(
        "ix_pricing_import_batches__tenant_case",
        "pricing_import_batches",
        ["tenant_id", "case_id", "created_at"],
    )
    op.create_table(
        "pricing_import_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("row_number", sa.Integer, nullable=False),
        sa.Column("code", sa.String(length=120), nullable=True),
        sa.Column("designation", sa.String(length=500), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("quantity_decimal", sa.String(length=32), nullable=False),
        sa.Column("unit_price_minor", sa.BigInteger, nullable=False),
        sa.Column("total_minor", sa.BigInteger, nullable=False),
        sa.Column("error_codes_json", postgresql.JSONB, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_pricing_import_rows"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_pricing_import_rows__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "batch_id"],
            ["pricing_import_batches.tenant_id", "pricing_import_batches.id"],
            name="fk_pricing_import_rows__batch",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_pricing_import_rows__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "batch_id", "row_number", name="uq_pricing_import_row_number"
        ),
        sa.CheckConstraint("row_number >= 1", name="row_number_positive"),
        sa.CheckConstraint("length(trim(designation)) > 0", name="designation"),
        sa.CheckConstraint("quantity_decimal <> ''", name="quantity_decimal_non_empty"),
        sa.CheckConstraint("unit_price_minor >= 0", name="unit_price_non_negative"),
        sa.CheckConstraint("total_minor >= 0", name="total_non_negative"),
    )
    op.create_index("ix_pricing_import_rows_tenant_id", "pricing_import_rows", ["tenant_id"])
    op.create_index(
        "ix_pricing_import_rows__tenant_batch",
        "pricing_import_rows",
        ["tenant_id", "batch_id", "row_number"],
    )
    op.execute("""
        CREATE FUNCTION prevent_pricing_import_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'pricing import records are append-only';
        END;
        $$;
        CREATE TRIGGER pricing_import_batches_append_only
        BEFORE UPDATE OR DELETE ON pricing_import_batches
        FOR EACH ROW EXECUTE FUNCTION prevent_pricing_import_mutation();
        CREATE TRIGGER pricing_import_rows_append_only
        BEFORE UPDATE OR DELETE ON pricing_import_rows
        FOR EACH ROW EXECUTE FUNCTION prevent_pricing_import_mutation();
    """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS pricing_import_rows_append_only ON pricing_import_rows"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS pricing_import_batches_append_only ON pricing_import_batches"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_pricing_import_mutation()")
    op.execute("DROP INDEX IF EXISTS ix_pricing_import_rows__tenant_batch")
    op.execute("DROP INDEX IF EXISTS ix_pricing_import_rows_tenant_id")
    op.drop_table("pricing_import_rows")
    op.execute("DROP INDEX IF EXISTS ix_pricing_import_batches__tenant_case")
    op.execute("DROP INDEX IF EXISTS ix_pricing_import_batches_tenant_id")
    op.drop_table("pricing_import_batches")
