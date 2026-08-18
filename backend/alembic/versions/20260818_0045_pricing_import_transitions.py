"""Create append-only pricing import lifecycle transitions.

Revision ID: 20260818_0045
Revises: 20260818_0044
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260818_0045"
down_revision = "20260818_0044"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pricing_import_transitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_state", sa.String(length=16), nullable=False),
        sa.Column("to_state", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_pricing_import_transitions"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_pricing_import_transitions__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "batch_id"],
            ["pricing_import_batches.tenant_id", "pricing_import_batches.id"],
            name="fk_pricing_import_transitions__batch",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uq_pricing_import_transitions__tenant_id"
        ),
        sa.UniqueConstraint(
            "tenant_id", "batch_id", "version", name="uq_pricing_import_transition_version"
        ),
        sa.UniqueConstraint(
            "tenant_id", "command_id", name="uq_pricing_import_transition_command"
        ),
        sa.CheckConstraint("version > 1", name="version_positive"),
        sa.CheckConstraint("from_state = 'PREVIEWED'", name="from_state"),
        sa.CheckConstraint("to_state = 'COMMITTED'", name="to_state"),
    )
    op.create_index(
        "ix_pricing_import_transitions_tenant_id",
        "pricing_import_transitions",
        ["tenant_id"],
    )
    op.create_index(
        "ix_pricing_import_transitions__tenant_batch_version",
        "pricing_import_transitions",
        ["tenant_id", "batch_id", "version"],
    )
    op.execute("""
        CREATE FUNCTION prevent_pricing_import_transition_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'pricing import transitions are append-only';
        END;
        $$;
        CREATE TRIGGER pricing_import_transitions_append_only
        BEFORE UPDATE OR DELETE ON pricing_import_transitions
        FOR EACH ROW EXECUTE FUNCTION prevent_pricing_import_transition_mutation();
    """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS pricing_import_transitions_append_only "
        "ON pricing_import_transitions"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_pricing_import_transition_mutation()")
    op.execute("DROP INDEX IF EXISTS ix_pricing_import_transitions__tenant_batch_version")
    op.execute("DROP INDEX IF EXISTS ix_pricing_import_transitions_tenant_id")
    op.drop_table("pricing_import_transitions")
