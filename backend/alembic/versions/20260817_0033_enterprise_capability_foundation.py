"""Create enterprise capability roots, immutable versions and proof links.

Revision ID: 20260817_0033
Revises: 20260817_0032
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260817_0033"
down_revision = "20260817_0032"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "enterprise_capabilities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("capability_kind", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("summary", sa.String(length=1000), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_enterprise_capability__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "company_id"],
            ["enterprise_companies.tenant_id", "enterprise_companies.id"],
            name="fk_enterprise_capability__company",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_enterprise_capabilities"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_enterprise_capability__tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_enterprise_capability__command"),
        sa.UniqueConstraint(
            "tenant_id",
            "company_id",
            "capability_kind",
            "name",
            name="uq_enterprise_capability__identity",
        ),
        sa.CheckConstraint(
            "capability_kind IN ('QUALIFICATION', 'REFERENCE', 'EQUIPMENT', 'TEAM', 'METHOD')",
            name="capability_kind",
        ),
        sa.CheckConstraint("state IN ('ACTIVE', 'SUSPENDED', 'RETIRED')", name="state"),
        sa.CheckConstraint("aggregate_revision >= 0", name="aggregate_revision"),
    )
    op.create_index(
        "ix_enterprise_capabilities_tenant_id", "enterprise_capabilities", ["tenant_id"]
    )
    op.create_index(
        "ix_enterprise_capabilities__tenant_company_kind_state",
        "enterprise_capabilities",
        ["tenant_id", "company_id", "capability_kind", "state"],
    )

    op.create_table(
        "enterprise_capability_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("capability_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_scope", sa.String(length=500), nullable=False),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id", "capability_id"],
            ["enterprise_capabilities.tenant_id", "enterprise_capabilities.id"],
            name="fk_enterprise_capability_version__capability",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_enterprise_capability_version__membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_enterprise_capability_versions"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_enterprise_capability_version__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "command_id", name="uq_enterprise_capability_version__command"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "capability_id",
            "version_number",
            name="uq_enterprise_capability_version__number",
        ),
        sa.CheckConstraint("version_number > 0", name="version_number"),
        sa.CheckConstraint("valid_until IS NULL OR valid_until > valid_from", name="validity"),
    )
    op.create_index(
        "ix_enterprise_capability_versions_tenant_id",
        "enterprise_capability_versions",
        ["tenant_id"],
    )
    op.create_index(
        "ix_enterprise_capability_versions__tenant_capability_validity",
        "enterprise_capability_versions",
        ["tenant_id", "capability_id", "valid_until"],
    )

    op.create_table(
        "enterprise_capability_proof_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("capability_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relation_label", sa.String(length=240), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "capability_version_id"],
            ["enterprise_capability_versions.tenant_id", "enterprise_capability_versions.id"],
            name="fk_enterprise_capability_proof_link__version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["enterprise_documents.tenant_id", "enterprise_documents.id"],
            name="fk_enterprise_capability_proof_link__document",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_enterprise_capability_proof_links"),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uq_enterprise_capability_proof_link__tenant_id"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "capability_version_id",
            "document_id",
            name="uq_enterprise_capability_proof_link__identity",
        ),
        sa.CheckConstraint("length(trim(relation_label)) > 0", name="relation_label"),
    )
    op.create_index(
        "ix_enterprise_capability_proof_links_tenant_id",
        "enterprise_capability_proof_links",
        ["tenant_id"],
    )

    op.execute(
        """
        CREATE FUNCTION prevent_enterprise_capability_version_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'enterprise capability versions are append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER enterprise_capability_versions_append_only
        BEFORE UPDATE OR DELETE ON enterprise_capability_versions
        FOR EACH ROW EXECUTE FUNCTION prevent_enterprise_capability_version_mutation();
        """
    )
    op.execute(
        """
        CREATE FUNCTION prevent_enterprise_capability_proof_link_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'enterprise capability proof links are append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER enterprise_capability_proof_links_append_only
        BEFORE UPDATE OR DELETE ON enterprise_capability_proof_links
        FOR EACH ROW EXECUTE FUNCTION prevent_enterprise_capability_proof_link_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS enterprise_capability_proof_links_append_only "
        "ON enterprise_capability_proof_links"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_enterprise_capability_proof_link_mutation()")
    op.execute(
        "DROP TRIGGER IF EXISTS enterprise_capability_versions_append_only "
        "ON enterprise_capability_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_enterprise_capability_version_mutation()")
    op.execute("DROP INDEX IF EXISTS ix_enterprise_capability_proof_links_tenant_id")
    op.drop_table("enterprise_capability_proof_links")
    op.execute("DROP INDEX IF EXISTS ix_enterprise_capability_versions__tenant_capability_validity")
    op.execute("DROP INDEX IF EXISTS ix_enterprise_capability_versions_tenant_id")
    op.drop_table("enterprise_capability_versions")
    op.execute("DROP INDEX IF EXISTS ix_enterprise_capabilities__tenant_company_kind_state")
    op.execute("DROP INDEX IF EXISTS ix_enterprise_capabilities_tenant_id")
    op.drop_table("enterprise_capabilities")
