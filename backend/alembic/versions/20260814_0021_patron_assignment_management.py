"""Create the append-only patron assignment authority journal."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260814_0021"
down_revision = "20260814_0020"
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
    op.drop_index("ux_assignments__active_member_case", table_name="case_assignments")
    op.create_index(
        "ux_assignments__open_member_case",
        "case_assignments",
        ["tenant_id", "membership_id", "case_id"],
        unique=True,
        postgresql_where=sa.text("state IN ('ACTIVE', 'SUSPENDED')"),
    )

    created_at, updated_at = _timestamps()
    op.create_table(
        "case_assignment_change_events",
        sa.Column("id", _UUID, nullable=False),
        sa.Column("tenant_id", _UUID, nullable=False),
        sa.Column("assignment_id", _UUID, nullable=False),
        sa.Column("case_id", _UUID, nullable=False),
        sa.Column("target_membership_id", _UUID, nullable=False),
        sa.Column("author_membership_id", _UUID, nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("previous_revision", sa.Integer(), nullable=True),
        sa.Column("resulting_revision", sa.Integer(), nullable=False),
        sa.Column("previous_state", sa.String(16), nullable=True),
        sa.Column("resulting_state", sa.String(16), nullable=False),
        sa.Column("reason_code", sa.String(40), nullable=True),
        sa.Column(
            "previous_scope_actions_json",
            postgresql.JSONB(none_as_null=True),
            nullable=True,
        ),
        sa.Column(
            "previous_scope_classifications_json",
            postgresql.JSONB(none_as_null=True),
            nullable=True,
        ),
        sa.Column("resulting_scope_actions_json", postgresql.JSONB(), nullable=False),
        sa.Column("resulting_scope_classifications_json", postgresql.JSONB(), nullable=False),
        sa.Column("command_id", _UUID, nullable=False),
        sa.Column("correlation_id", _UUID, nullable=True),
        created_at,
        updated_at,
        sa.CheckConstraint(
            "event_type IN ('ASSIGNMENT_CREATED', 'ASSIGNMENT_SCOPE_AMENDED', "
            "'ASSIGNMENT_SUSPENDED', 'ASSIGNMENT_REACTIVATED', 'ASSIGNMENT_ENDED')",
            name="event_type",
        ),
        sa.CheckConstraint(
            "resulting_revision >= 0 AND (previous_revision IS NULL OR previous_revision >= 0) "
            "AND ((event_type = 'ASSIGNMENT_CREATED' AND previous_revision IS NULL "
            "AND resulting_revision = 0) OR (event_type <> 'ASSIGNMENT_CREATED' "
            "AND previous_revision IS NOT NULL "
            "AND resulting_revision = previous_revision + 1))",
            name="revision",
        ),
        sa.CheckConstraint(
            "(previous_state IS NULL OR previous_state IN ('ACTIVE', 'SUSPENDED', "
            "'ENDED', 'EXPIRED')) AND resulting_state IN ('ACTIVE', 'SUSPENDED', "
            "'ENDED', 'EXPIRED')",
            name="state",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(resulting_scope_actions_json) = 'array' "
            "AND jsonb_array_length(resulting_scope_actions_json) > 0 "
            "AND jsonb_typeof(resulting_scope_classifications_json) = 'array' "
            "AND jsonb_array_length(resulting_scope_classifications_json) > 0",
            name="scope_result",
        ),
        sa.CheckConstraint(
            "(previous_scope_actions_json IS NULL AND previous_scope_classifications_json "
            "IS NULL) OR (jsonb_typeof(previous_scope_actions_json) = 'array' "
            "AND jsonb_array_length(previous_scope_actions_json) > 0 "
            "AND jsonb_typeof(previous_scope_classifications_json) = 'array' "
            "AND jsonb_array_length(previous_scope_classifications_json) > 0)",
            name="scope_previous",
        ),
        sa.CheckConstraint(
            "reason_code IS NULL OR reason_code IN ('PATRON_SUSPENDED', "
            "'WORKLOAD_REALLOCATION', 'CASE_PAUSED', 'ACCESS_REVIEW', 'PATRON_ENDED', "
            "'CASE_STOPPED', 'CASE_ARCHIVED', 'COLLABORATOR_UNAVAILABLE', "
            "'MEMBERSHIP_REVOKED')",
            name="reason",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_assignment_change__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["case_assignments.tenant_id", "case_assignments.id"],
            name="fk_assignment_change__assignment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_assignment_change__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "target_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_assignment_change__target_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "author_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_assignment_change__author_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_case_assignment_change_events"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_assignment_change__tenant_id"),
    )
    op.create_index(
        "ix_assignment_change__tenant_assignment",
        "case_assignment_change_events",
        ["tenant_id", "assignment_id", "created_at"],
    )
    op.create_index(
        "ix_assignment_change__tenant_case_target",
        "case_assignment_change_events",
        ["tenant_id", "case_id", "target_membership_id", "created_at"],
    )
    op.create_index(
        "ix_case_assignment_change_events_tenant_id",
        "case_assignment_change_events",
        ["tenant_id"],
    )
    op.execute(
        "CREATE FUNCTION prevent_case_assignment_change_event_mutation() RETURNS trigger AS $$ "
        "BEGIN RAISE EXCEPTION 'CASE_ASSIGNMENT_CHANGE_EVENT_APPEND_ONLY'; END; $$ "
        "LANGUAGE plpgsql;"
    )
    op.execute(
        "CREATE TRIGGER trg_case_assignment_change_events_append_only BEFORE UPDATE OR DELETE "
        "ON case_assignment_change_events FOR EACH ROW EXECUTE FUNCTION "
        "prevent_case_assignment_change_event_mutation()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_case_assignment_change_events_append_only "
        "ON case_assignment_change_events"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_case_assignment_change_event_mutation()")
    op.drop_index(
        "ix_case_assignment_change_events_tenant_id",
        table_name="case_assignment_change_events",
    )
    op.drop_index(
        "ix_assignment_change__tenant_case_target",
        table_name="case_assignment_change_events",
    )
    op.drop_index(
        "ix_assignment_change__tenant_assignment",
        table_name="case_assignment_change_events",
    )
    op.drop_table("case_assignment_change_events")
    op.drop_index("ux_assignments__open_member_case", table_name="case_assignments")
    op.create_index(
        "ux_assignments__active_member_case",
        "case_assignments",
        ["tenant_id", "membership_id", "case_id"],
        unique=True,
        postgresql_where=sa.text("state = 'ACTIVE'"),
    )
