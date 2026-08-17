"""Create preparation readiness and generated technical document metadata.

Revision ID: 20260817_0032
Revises: 20260817_0031
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260817_0032"
down_revision = "20260817_0031"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _uuid(name: str) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=False)


def upgrade() -> None:
    op.create_table(
        "preparation_packages",
        _uuid("id"),
        _uuid("tenant_id"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        _uuid("case_id"),
        _uuid("assignment_id"),
        _uuid("dce_version_id"),
        sa.Column("state", sa.String(24), server_default="IN_PREPARATION", nullable=False),
        sa.Column("aggregate_revision", sa.Integer(), server_default="0", nullable=False),
        _uuid("created_by_actor_id"),
        _uuid("membership_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_prep_packages__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["case_assignments.tenant_id", "case_assignments.id"],
            name="fk_prep_packages__assignment",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_preparation_packages"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_prep_packages__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "case_id",
            "assignment_id",
            "dce_version_id",
            name="uq_prep_package_identity",
        ),
        sa.CheckConstraint(
            "state IN ('IN_PREPARATION', 'A_REVIEW', 'READY', 'BLOCKED', 'GENERATED')", name="state"
        ),
        sa.CheckConstraint("aggregate_revision >= 0", name="aggregate_revision"),
    )
    op.create_index("ix_preparation_packages_tenant_id", "preparation_packages", ["tenant_id"])
    op.create_index(
        "ix_prep_packages__tenant_case_state",
        "preparation_packages",
        ["tenant_id", "case_id", "state"],
    )

    op.create_table(
        "preparation_readiness",
        _uuid("id"),
        _uuid("tenant_id"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        _uuid("package_id"),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("blocker_codes_json", postgresql.JSONB(), nullable=False),
        sa.Column("warning_codes_json", postgresql.JSONB(), nullable=False),
        sa.Column("checked_requirement_count", sa.Integer(), nullable=False),
        sa.Column("checked_task_count", sa.Integer(), nullable=False),
        sa.Column("input_manifest_sha256", sa.CHAR(64), nullable=False),
        sa.Column("evaluator_id", sa.String(100), nullable=False),
        sa.Column("evaluator_version", sa.String(64), nullable=False),
        _uuid("actor_id"),
        _uuid("membership_id"),
        _uuid("command_id"),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_prep_readiness__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "package_id"],
            ["preparation_packages.tenant_id", "preparation_packages.id"],
            name="fk_prep_readiness__package",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_preparation_readiness"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_prep_readiness__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "package_id", "revision", name="uq_prep_readiness_revision"
        ),
        sa.CheckConstraint("revision > 0", name="revision_positive"),
        sa.CheckConstraint("state IN ('READY', 'READY_WITH_WARNINGS', 'BLOCKED')", name="state"),
        sa.CheckConstraint("checked_requirement_count >= 0", name="requirements_nonnegative"),
        sa.CheckConstraint("checked_task_count >= 0", name="tasks_nonnegative"),
    )
    op.create_index("ix_preparation_readiness_tenant_id", "preparation_readiness", ["tenant_id"])
    op.create_index(
        "ix_prep_readiness__tenant_package_revision",
        "preparation_readiness",
        ["tenant_id", "package_id", "revision"],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_preparation_readiness_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'preparation readiness is append-only'; END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER preparation_readiness_append_only
        BEFORE UPDATE OR DELETE ON preparation_readiness
        FOR EACH ROW EXECUTE FUNCTION prevent_preparation_readiness_mutation();
        """
    )

    op.create_table(
        "generated_technical_documents",
        _uuid("id"),
        _uuid("tenant_id"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        _uuid("package_id"),
        _uuid("readiness_id"),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("document_kind", sa.String(32), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("content_sha256", sa.CHAR(64), nullable=False),
        sa.Column("storage_key", sa.String(700), nullable=False),
        _uuid("actor_id"),
        _uuid("membership_id"),
        _uuid("command_id"),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_generated_docs__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "package_id"],
            ["preparation_packages.tenant_id", "preparation_packages.id"],
            name="fk_generated_docs__package",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "readiness_id"],
            ["preparation_readiness.tenant_id", "preparation_readiness.id"],
            name="fk_generated_docs__readiness",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_generated_technical_documents"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_generated_docs__tenant_id"),
        sa.UniqueConstraint("tenant_id", "package_id", "version", name="uq_generated_doc_version"),
        sa.CheckConstraint("version > 0", name="version_positive"),
        sa.CheckConstraint("document_kind IN ('TECHNICAL_RESPONSE')", name="document_kind"),
        sa.CheckConstraint("state IN ('GENERATED', 'FAILED_SAFE')", name="state"),
    )
    op.create_index(
        "ix_generated_technical_documents_tenant_id", "generated_technical_documents", ["tenant_id"]
    )
    op.create_index(
        "ix_generated_docs__tenant_package_version",
        "generated_technical_documents",
        ["tenant_id", "package_id", "version"],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_generated_technical_document_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'generated technical documents are append-only'; END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER generated_technical_documents_append_only
        BEFORE UPDATE OR DELETE ON generated_technical_documents
        FOR EACH ROW EXECUTE FUNCTION prevent_generated_technical_document_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS generated_technical_documents_append_only "
        "ON generated_technical_documents"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_generated_technical_document_mutation()")
    op.drop_index(
        "ix_generated_docs__tenant_package_version", table_name="generated_technical_documents"
    )
    op.execute("DROP INDEX IF EXISTS ix_generated_technical_documents_tenant_id")
    op.drop_table("generated_technical_documents")
    op.execute("DROP TRIGGER IF EXISTS preparation_readiness_append_only ON preparation_readiness")
    op.execute("DROP FUNCTION IF EXISTS prevent_preparation_readiness_mutation()")
    op.drop_index("ix_prep_readiness__tenant_package_revision", table_name="preparation_readiness")
    op.execute("DROP INDEX IF EXISTS ix_preparation_readiness_tenant_id")
    op.drop_table("preparation_readiness")
    op.drop_index("ix_prep_packages__tenant_case_state", table_name="preparation_packages")
    op.execute("DROP INDEX IF EXISTS ix_preparation_packages_tenant_id")
    op.drop_table("preparation_packages")
