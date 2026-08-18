"""Create append-only submission signature intents and proofs.

Revision ID: 20260818_0047
Revises: 20260818_0046
Create Date: 2026-08-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260818_0047"
down_revision = "20260818_0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "submission_signatures",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submission_package_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("signer_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expected_package_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("provider_reference_hash", sa.CHAR(length=64), nullable=True),
        sa.Column("signature_sha256", sa.CHAR(length=64), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "submission_package_id"],
            ["submission_packages.tenant_id", "submission_packages.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uq_submission_signatures__tenant_id"
        ),
        sa.UniqueConstraint(
            "tenant_id", "command_id", name="uq_submission_signatures__tenant_command"
        ),
        sa.CheckConstraint("status IN ('REQUESTED', 'SIGNED', 'REJECTED')", name="status"),
        sa.CheckConstraint("expected_package_version > 0", name="expected_package_version"),
        sa.CheckConstraint(
            "provider_reference_hash IS NULL OR provider_reference_hash ~ '^[a-f0-9]{64}$'",
            name="provider_reference_hash",
        ),
        sa.CheckConstraint(
            "signature_sha256 IS NULL OR signature_sha256 ~ '^[a-f0-9]{64}$'",
            name="signature_sha256",
        ),
    )
    op.create_index(
        "ix_submission_signatures_tenant_id", "submission_signatures", ["tenant_id"]
    )
    op.create_index(
        "ix_submission_signatures__tenant_package",
        "submission_signatures",
        ["tenant_id", "submission_package_id"],
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_submission_signature_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'submission signature is append-only';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_submission_signature_append_only
        BEFORE UPDATE OR DELETE ON submission_signatures
        FOR EACH ROW EXECUTE FUNCTION prevent_submission_signature_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_submission_signature_append_only ON submission_signatures"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_submission_signature_mutation()")
    op.execute(
        "DROP INDEX IF EXISTS ix_submission_signatures__tenant_package"
    )
    op.execute("DROP INDEX IF EXISTS ix_submission_signatures_tenant_id")
    op.drop_table("submission_signatures")
