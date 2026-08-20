"""Create immutable manual submission evidence.

Revision ID: 20260818_0040
Revises: 20260818_0039
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260818_0040"
down_revision = "20260818_0039"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "submission_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("submission_package_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("external_reference_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("evidence_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("notes_redacted", sa.String(length=1000), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_submission_evidence"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "submission_package_id"],
            ["submission_packages.tenant_id", "submission_packages.id"],
            name="fk_submission_evidence__package",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_submission_evidence__tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_submission_evidence__command"),
        sa.CheckConstraint(
            "evidence_type IN ('MANUAL_RECEIPT', 'MANUAL_PORTAL_REFERENCE')",
            name="evidence_type",
        ),
        sa.CheckConstraint("status IN ('RECEIVED', 'REJECTED')", name="status"),
    )
    op.create_index("ix_submission_evidence_tenant_id", "submission_evidence", ["tenant_id"])
    op.create_index(
        "ix_submission_evidence__tenant_package",
        "submission_evidence",
        ["tenant_id", "submission_package_id"],
    )
    op.execute("""
        CREATE FUNCTION prevent_submission_evidence_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'submission evidence is append-only';
        END;
        $$;
        CREATE TRIGGER submission_evidence_append_only
        BEFORE UPDATE OR DELETE ON submission_evidence
        FOR EACH ROW EXECUTE FUNCTION prevent_submission_evidence_mutation();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS submission_evidence_append_only ON submission_evidence")
    op.execute("DROP FUNCTION IF EXISTS prevent_submission_evidence_mutation()")
    op.drop_index("ix_submission_evidence__tenant_package", table_name="submission_evidence")
    op.drop_index("ix_submission_evidence_tenant_id", table_name="submission_evidence")
    op.drop_table("submission_evidence")
