"""Create append-only pricing scenario transitions.

Revision ID: 20260818_0042
Revises: 20260818_0041
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260818_0042"
down_revision = "20260818_0041"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pricing_scenario_transitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_state", sa.String(length=16), nullable=False),
        sa.Column("to_state", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_pricing_scenario_transitions"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "scenario_id"],
            ["pricing_scenarios.tenant_id", "pricing_scenarios.id"],
            name="fk_pricing_scenario_transitions__scenario",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_pricing_scenario_transitions__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "scenario_id", "version", name="uq_pricing_scenario_transitions__version"
        ),
        sa.UniqueConstraint(
            "tenant_id", "command_id", name="uq_pricing_scenario_transitions__command"
        ),
        sa.CheckConstraint("version > 1", name="version_positive"),
        sa.CheckConstraint("from_state IN ('DRAFT', 'SELECTED')", name="from_state"),
        sa.CheckConstraint("to_state IN ('SELECTED', 'ARCHIVED')", name="to_state"),
    )
    op.create_index(
        "ix_pricing_scenario_transitions_tenant_id", "pricing_scenario_transitions", ["tenant_id"]
    )
    op.create_index(
        "ix_pricing_scenario_transitions__tenant_scenario_version",
        "pricing_scenario_transitions",
        ["tenant_id", "scenario_id", "version"],
    )
    op.execute("""
        CREATE FUNCTION prevent_pricing_scenario_transition_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'pricing scenario transitions are append-only';
        END;
        $$;
        CREATE TRIGGER pricing_scenario_transitions_append_only
        BEFORE UPDATE OR DELETE ON pricing_scenario_transitions
        FOR EACH ROW EXECUTE FUNCTION prevent_pricing_scenario_transition_mutation();
    """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS pricing_scenario_transitions_append_only "
        "ON pricing_scenario_transitions"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_pricing_scenario_transition_mutation()")
    op.drop_index(
        "ix_pricing_scenario_transitions__tenant_scenario_version",
        table_name="pricing_scenario_transitions",
    )
    op.drop_index(
        "ix_pricing_scenario_transitions_tenant_id", table_name="pricing_scenario_transitions"
    )
    op.drop_table("pricing_scenario_transitions")
