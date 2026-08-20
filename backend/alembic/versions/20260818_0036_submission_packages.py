"""submission package preparation

Revision ID: 20260818_0036
Revises: 20260817_0035
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260818_0036"
down_revision = "20260817_0035"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "submission_packages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("preparation_package_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dce_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("technical_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("technical_document_version", sa.Integer, nullable=False),
        sa.Column("financial_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("financial_snapshot_revision", sa.Integer, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("manifest_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("manifest_json", postgresql.JSONB, nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_submission_package__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "preparation_package_id"],
            ["preparation_packages.tenant_id", "preparation_packages.id"],
            name="fk_submission_package__preparation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "technical_document_id"],
            ["generated_technical_documents.tenant_id", "generated_technical_documents.id"],
            name="fk_submission_package__document",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "financial_snapshot_id"],
            ["financial_report_snapshots.tenant_id", "financial_report_snapshots.id"],
            name="fk_submission_package__financial_snapshot",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_submission_packages"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_submission_package__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "preparation_package_id",
            "version",
            name="uq_submission_package__preparation_version",
        ),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_submission_package__command"),
        sa.CheckConstraint("version > 0", name="version_positive"),
        sa.CheckConstraint(
            "state IN ('PRET_CONTROLE', 'AUTORISE_DEPOT')",
            name="state",
        ),
        sa.CheckConstraint("technical_document_version > 0", name="technical_document_version"),
        sa.CheckConstraint("financial_snapshot_revision >= 0", name="financial_snapshot_revision"),
    )
    op.create_index(
        "ix_submission_packages_tenant_id", "submission_packages", ["tenant_id"]
    )
    op.create_index(
        "ix_submission_packages__tenant_preparation_version",
        "submission_packages",
        ["tenant_id", "preparation_package_id", "version"],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_submission_package_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'submission package is append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER submission_packages_append_only
        BEFORE UPDATE OR DELETE ON submission_packages
        FOR EACH ROW EXECUTE FUNCTION prevent_submission_package_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS submission_packages_append_only ON submission_packages")
    op.execute("DROP FUNCTION IF EXISTS prevent_submission_package_mutation()")
    op.execute(
        "DROP INDEX IF EXISTS ix_submission_packages__tenant_preparation_version"
    )
    op.execute("DROP INDEX IF EXISTS ix_submission_packages_tenant_id")
    op.drop_table("submission_packages")
