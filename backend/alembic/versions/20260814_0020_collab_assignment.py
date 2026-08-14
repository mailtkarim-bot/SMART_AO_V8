"""Create COLLAB-ASSIGNMENT-01 immutable interaction histories."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260814_0020"
down_revision = "20260814_0019"
branch_labels = None
depends_on = None

_UUID = postgresql.UUID(as_uuid=True)


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def upgrade() -> None:
    op.add_column(
        "case_assignments",
        sa.Column("aggregate_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "aggregate_revision",
        "case_assignments",
        "aggregate_revision >= 0",
    )

    ack_created_at, ack_updated_at = _timestamps()
    op.create_table(
        "case_assignment_acknowledgements",
        sa.Column("id", _UUID, nullable=False),
        sa.Column("tenant_id", _UUID, nullable=False),
        sa.Column("assignment_id", _UUID, nullable=False),
        sa.Column("actor_id", _UUID, nullable=False),
        sa.Column("membership_id", _UUID, nullable=False),
        sa.Column("assignment_revision", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("command_id", _UUID, nullable=False),
        sa.Column("correlation_id", _UUID, nullable=True),
        ack_created_at,
        ack_updated_at,
        sa.CheckConstraint("assignment_revision >= 0", name="assignment_revision"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_assignment_ack__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["case_assignments.tenant_id", "case_assignments.id"],
            name="fk_assignment_ack__assignment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_assignment_ack__membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_case_assignment_acknowledgements"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_assignment_ack__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "assignment_id",
            "actor_id",
            "assignment_revision",
            name="uq_assignment_ack__revision_actor",
        ),
    )
    op.create_index(
        "ix_assignment_ack__tenant_assignment",
        "case_assignment_acknowledgements",
        ["tenant_id", "assignment_id", "created_at"],
    )
    op.create_index(
        "ix_case_assignment_acknowledgements_tenant_id",
        "case_assignment_acknowledgements",
        ["tenant_id"],
    )

    clarification_created_at, clarification_updated_at = _timestamps()
    op.create_table(
        "assignment_clarification_requests",
        sa.Column("id", _UUID, nullable=False),
        sa.Column("tenant_id", _UUID, nullable=False),
        sa.Column("assignment_id", _UUID, nullable=False),
        sa.Column("case_id", _UUID, nullable=False),
        sa.Column("actor_id", _UUID, nullable=False),
        sa.Column("membership_id", _UUID, nullable=False),
        sa.Column("clarification_kind", sa.String(32), nullable=False),
        sa.Column("subject", sa.String(160), nullable=False),
        sa.Column("question", sa.String(2_000), nullable=False),
        sa.Column("requested_scope", sa.String(500), nullable=True),
        sa.Column("priority", sa.String(16), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="OPEN"),
        sa.Column("functional_key", sa.CHAR(64), nullable=False),
        sa.Column("command_id", _UUID, nullable=False),
        sa.Column("correlation_id", _UUID, nullable=True),
        clarification_created_at,
        clarification_updated_at,
        sa.CheckConstraint(
            "clarification_kind IN ('SCOPE', 'PRIORITY', 'DEADLINE', 'DOCUMENT', "
            "'RESPONSIBILITY', 'OTHER')",
            name="clarification_kind",
        ),
        sa.CheckConstraint("priority IN ('LOW', 'NORMAL', 'HIGH')", name="priority"),
        sa.CheckConstraint("state = 'OPEN'", name="state_open_only"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_assignment_clarification__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["case_assignments.tenant_id", "case_assignments.id"],
            name="fk_assignment_clarification__assignment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_assignment_clarification__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_assignment_clarification__membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assignment_clarification_requests"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_assignment_clarification__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "functional_key", name="uq_assignment_clarification__functional_key"
        ),
    )
    op.create_index(
        "ix_assignment_clarification__tenant_assignment",
        "assignment_clarification_requests",
        ["tenant_id", "assignment_id", "created_at"],
    )
    op.create_index(
        "ix_assignment_clarification_requests_tenant_id",
        "assignment_clarification_requests",
        ["tenant_id"],
    )

    unavailability_created_at, unavailability_updated_at = _timestamps()
    op.create_table(
        "case_assignment_unavailabilities",
        sa.Column("id", _UUID, nullable=False),
        sa.Column("tenant_id", _UUID, nullable=False),
        sa.Column("assignment_id", _UUID, nullable=False),
        sa.Column("actor_id", _UUID, nullable=False),
        sa.Column("membership_id", _UUID, nullable=False),
        sa.Column("assignment_revision", sa.Integer(), nullable=False),
        sa.Column("reason_kind", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(2_000), nullable=False),
        sa.Column("unavailable_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unavailable_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("known_deadline_impact", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("impact_note", sa.String(500), nullable=True),
        sa.Column("command_id", _UUID, nullable=False),
        sa.Column("correlation_id", _UUID, nullable=True),
        unavailability_created_at,
        unavailability_updated_at,
        sa.CheckConstraint(
            "reason_kind IN ('SICKNESS', 'LEAVE', 'CAPACITY_CONFLICT', 'SKILL_GAP', "
            "'ACCESS_PROBLEM', 'OTHER')",
            name="reason_kind",
        ),
        sa.CheckConstraint(
            "unavailable_until IS NULL OR unavailable_until > unavailable_from",
            name="period_ordered",
        ),
        sa.CheckConstraint(
            "known_deadline_impact = FALSE OR NULLIF(BTRIM(impact_note), '') IS NOT NULL",
            name="impact_note_required",
        ),
        sa.CheckConstraint("assignment_revision >= 0", name="assignment_revision"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_assignment_unavailability__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["case_assignments.tenant_id", "case_assignments.id"],
            name="fk_assignment_unavailability__assignment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_assignment_unavailability__membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_case_assignment_unavailabilities"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_assignment_unavailability__tenant_id"),
    )
    op.create_index(
        "ix_assignment_unavailability__tenant_assignment",
        "case_assignment_unavailabilities",
        ["tenant_id", "assignment_id", "created_at"],
    )
    op.create_index(
        "ix_case_assignment_unavailabilities_tenant_id",
        "case_assignment_unavailabilities",
        ["tenant_id"],
    )

    op.execute(
        "CREATE FUNCTION prevent_case_assignment_history_mutation() RETURNS trigger AS $$ "
        "BEGIN RAISE EXCEPTION 'CASE_ASSIGNMENT_HISTORY_APPEND_ONLY'; END; $$ LANGUAGE plpgsql;"
    )
    for table in (
        "case_assignment_acknowledgements",
        "assignment_clarification_requests",
        "case_assignment_unavailabilities",
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION prevent_case_assignment_history_mutation()"
        )


def downgrade() -> None:
    for table in (
        "case_assignment_acknowledgements",
        "assignment_clarification_requests",
        "case_assignment_unavailabilities",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    op.execute("DROP FUNCTION IF EXISTS prevent_case_assignment_history_mutation()")

    op.drop_index(
        "ix_case_assignment_unavailabilities_tenant_id",
        table_name="case_assignment_unavailabilities",
    )
    op.drop_index(
        "ix_assignment_unavailability__tenant_assignment",
        table_name="case_assignment_unavailabilities",
    )
    op.drop_table("case_assignment_unavailabilities")

    op.drop_index(
        "ix_assignment_clarification_requests_tenant_id",
        table_name="assignment_clarification_requests",
    )
    op.drop_index(
        "ix_assignment_clarification__tenant_assignment",
        table_name="assignment_clarification_requests",
    )
    op.drop_table("assignment_clarification_requests")

    op.drop_index(
        "ix_case_assignment_acknowledgements_tenant_id",
        table_name="case_assignment_acknowledgements",
    )
    op.drop_index(
        "ix_assignment_ack__tenant_assignment",
        table_name="case_assignment_acknowledgements",
    )
    op.drop_table("case_assignment_acknowledgements")

    op.drop_constraint("aggregate_revision", "case_assignments", type_="check")
    op.drop_column("case_assignments", "aggregate_revision")
