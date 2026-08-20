"""Create patron enterprise company and document library.

Revision ID: 20260817_0028
Revises: 20260816_0027
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260817_0028"
down_revision = "20260816_0027"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "enterprise_companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("aggregate_revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("legal_name", sa.String(length=240), nullable=False),
        sa.Column("trade_name", sa.String(length=240), nullable=True),
        sa.Column("siren", sa.CHAR(length=9), nullable=False),
        sa.Column("siret", sa.CHAR(length=14), nullable=False),
        sa.Column("vat_number", sa.String(length=34), nullable=False),
        sa.Column("address_line1", sa.String(length=240), nullable=False),
        sa.Column("postal_code", sa.String(length=16), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("country_code", sa.CHAR(length=2), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_enterprise_company__tenant", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_enterprise_companies"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_enterprise_company__tenant_id"),
        sa.UniqueConstraint("tenant_id", name="uq_enterprise_company__tenant"),
        sa.UniqueConstraint("tenant_id", "siren", name="uq_enterprise_company__tenant_siren"),
        sa.UniqueConstraint("tenant_id", "siret", name="uq_enterprise_company__tenant_siret"),
        sa.CheckConstraint("siren ~ '^[0-9]{9}$'", name="siren"),
        sa.CheckConstraint("siret ~ '^[0-9]{14}$'", name="siret"),
        sa.CheckConstraint("vat_number ~ '^[A-Z]{2}[A-Z0-9]{2,30}$'", name="vat_number"),
        sa.CheckConstraint("country_code ~ '^[A-Z]{2}$'", name="country_code"),
        sa.CheckConstraint("aggregate_revision >= 0", name="aggregate_revision"),
    )
    op.create_index("ix_enterprise_companies_tenant_id", "enterprise_companies", ["tenant_id"])

    op.create_table(
        "enterprise_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_kind", sa.String(length=16), nullable=False),
        sa.Column("document_label", sa.String(length=240), nullable=False),
        sa.Column("storage_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("verification_status", sa.String(length=16), nullable=False),
        sa.Column("registered_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_enterprise_document__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "company_id"],
            ["enterprise_companies.tenant_id", "enterprise_companies.id"],
            name="fk_enterprise_document__company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "registered_by_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_enterprise_document__membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_enterprise_documents"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_enterprise_document__tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_enterprise_document__command"),
        sa.CheckConstraint("document_kind IN ('INSURANCE', 'KBIS', 'RIB')", name="document_kind"),
        sa.CheckConstraint(
            "verification_status IN ('PENDING', 'VALIDATED', 'EXPIRED', 'REJECTED')",
            name="verification_status",
        ),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
        sa.CheckConstraint("expires_at IS NULL OR expires_at > issued_at", name="expiry"),
        sa.CheckConstraint(
            "(document_kind = 'RIB' AND expires_at IS NULL) OR document_kind <> 'RIB'",
            name="rib_expiry",
        ),
    )
    op.create_index("ix_enterprise_documents_tenant_id", "enterprise_documents", ["tenant_id"])
    op.create_index(
        "ix_enterprise_document__tenant_company_kind_expiry",
        "enterprise_documents",
        ["tenant_id", "company_id", "document_kind", "expires_at"],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_enterprise_document_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'enterprise documents are append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER enterprise_documents_append_only
        BEFORE UPDATE OR DELETE ON enterprise_documents
        FOR EACH ROW EXECUTE FUNCTION prevent_enterprise_document_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS enterprise_documents_append_only ON enterprise_documents")
    op.execute("DROP FUNCTION IF EXISTS prevent_enterprise_document_mutation()")
    op.execute(
        "DROP INDEX IF EXISTS ix_enterprise_document__tenant_company_kind_expiry"
    )
    op.execute("DROP INDEX IF EXISTS ix_enterprise_documents_tenant_id")
    op.drop_table("enterprise_documents")
    op.execute("DROP INDEX IF EXISTS ix_enterprise_companies_tenant_id")
    op.drop_table("enterprise_companies")
