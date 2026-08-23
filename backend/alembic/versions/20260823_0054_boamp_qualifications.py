"""Create append-only patron qualifications for BOAMP observations."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260823_0054"
down_revision = "20260823_0053"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "boamp_opportunity_qualifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("observation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(length=24), nullable=False),
        sa.Column("reason_code", sa.String(length=40), nullable=False),
        sa.Column("score_snapshot", sa.Integer(), nullable=False),
        sa.Column("score_version", sa.String(length=64), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="boamp_qualifications_tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "actor_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.identity_id"],
            name="boamp_qualifications_actor",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "observation_id"],
            ["boamp_opportunity_observations.tenant_id", "boamp_opportunity_observations.id"],
            name="boamp_qualifications_observation",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_boamp_opportunity_qualifications"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_boamp_qualifications_tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_boamp_qualifications_command"),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_boamp_qualifications_idempotency"
        ),
        sa.CheckConstraint(
            "decision IN ('QUALIFIED', 'REJECTED', 'SNOOZED')",
            name="boamp_qualifications_decision",
        ),
        sa.CheckConstraint(
            "reason_code IN ('RELEVANT_PUBLIC_SIGNAL', 'NOT_RELEVANT', "
            "'INSUFFICIENT_PUBLIC_DATA', 'EXPIRED')",
            name="boamp_qualifications_reason",
        ),
        sa.CheckConstraint("score_snapshot BETWEEN 0 AND 100", name="boamp_qualifications_score"),
        sa.CheckConstraint(
            "score_version = 'BOAMP_PUBLIC_V1'", name="boamp_qualifications_score_version"
        ),
    )
    op.create_index(
        "ix_boamp_qualifications_tenant_observation_created",
        "boamp_opportunity_qualifications",
        ["tenant_id", "observation_id", "created_at"],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_boamp_qualification_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'boamp qualifications are append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER boamp_qualifications_append_only
        BEFORE UPDATE OR DELETE ON boamp_opportunity_qualifications
        FOR EACH ROW EXECUTE FUNCTION prevent_boamp_qualification_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS boamp_qualifications_append_only "
        "ON boamp_opportunity_qualifications"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_boamp_qualification_mutation()")
    op.drop_index(
        "ix_boamp_qualifications_tenant_observation_created",
        table_name="boamp_opportunity_qualifications",
    )
    op.drop_table("boamp_opportunity_qualifications")
