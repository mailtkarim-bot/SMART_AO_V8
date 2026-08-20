"""Create immutable preparation snapshots and patron transmissions.

Revision ID: 20260818_0037
Revises: 20260818_0036
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260818_0037"
down_revision = "20260818_0036"
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
    op.create_table(
        "preparation_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("package_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dce_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("readiness_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("technical_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("technical_document_version", sa.Integer, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("manifest_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("manifest_json", postgresql.JSONB, nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_preparation_snapshots"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_prep_snapshots__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "package_id"],
            ["preparation_packages.tenant_id", "preparation_packages.id"],
            name="fk_prep_snapshots__package",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "readiness_id"],
            ["preparation_readiness.tenant_id", "preparation_readiness.id"],
            name="fk_prep_snapshots__readiness",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "technical_document_id"],
            ["generated_technical_documents.tenant_id", "generated_technical_documents.id"],
            name="fk_prep_snapshots__document",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_prep_snapshots__tenant_id"),
        sa.UniqueConstraint("tenant_id", "package_id", "version", name="uq_prep_snapshot__version"),
        sa.CheckConstraint("version > 0", name="version_positive"),
        sa.CheckConstraint("state IN ('READY_FOR_PATRON_REVIEW')", name="state"),
    )
    op.create_index(
        "ix_preparation_snapshots_tenant_id", "preparation_snapshots", ["tenant_id"]
    )
    op.create_index(
        "ix_prep_snapshots__tenant_package_version",
        "preparation_snapshots",
        ["tenant_id", "package_id", "version"],
    )

    op.create_table(
        "preparation_transmissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("package_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_preparation_transmissions"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_prep_transmissions__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "package_id"],
            ["preparation_packages.tenant_id", "preparation_packages.id"],
            name="fk_prep_transmissions__package",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "snapshot_id"],
            ["preparation_snapshots.tenant_id", "preparation_snapshots.id"],
            name="fk_prep_transmissions__snapshot",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_prep_transmissions__tenant_id"),
        sa.UniqueConstraint("tenant_id", "snapshot_id", name="uq_prep_transmission__snapshot"),
        sa.CheckConstraint("state IN ('TRANSMITTED_TO_PATRON')", name="state"),
    )
    op.create_index(
        "ix_preparation_transmissions_tenant_id", "preparation_transmissions", ["tenant_id"]
    )
    op.create_index(
        "ix_prep_transmissions__tenant_package",
        "preparation_transmissions",
        ["tenant_id", "package_id", "created_at"],
    )
    _append_only(
        "preparation_snapshots",
        "prevent_preparation_snapshot_mutation",
        "preparation_snapshots_append_only",
        "preparation snapshots are append-only",
    )
    _append_only(
        "preparation_transmissions",
        "prevent_preparation_transmission_mutation",
        "preparation_transmissions_append_only",
        "preparation transmissions are append-only",
    )


def downgrade() -> None:
    _drop_append_only(
        "preparation_transmissions",
        "prevent_preparation_transmission_mutation",
        "preparation_transmissions_append_only",
    )
    _drop_append_only(
        "preparation_snapshots",
        "prevent_preparation_snapshot_mutation",
        "preparation_snapshots_append_only",
    )
    op.drop_index(
        "ix_prep_transmissions__tenant_package",
        table_name="preparation_transmissions",
        if_exists=True,
    )
    op.drop_index(
        "ix_preparation_transmissions_tenant_id",
        table_name="preparation_transmissions",
        if_exists=True,
    )
    op.drop_table("preparation_transmissions")
    op.drop_index(
        "ix_prep_snapshots__tenant_package_version",
        table_name="preparation_snapshots",
        if_exists=True,
    )
    op.drop_index(
        "ix_preparation_snapshots_tenant_id",
        table_name="preparation_snapshots",
        if_exists=True,
    )
    op.drop_table("preparation_snapshots")
