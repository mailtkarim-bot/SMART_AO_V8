"""Create tenant-scoped collaborator Case assignments for SEC-01 ReBAC.

Revision ID: 20260813_0008
Revises: 20260813_0007
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260813_0008"
down_revision = "20260813_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_memberships__tenant_id",
        "tenant_memberships",
        ["tenant_id", "id"],
    )
    op.create_table(
        "case_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("scope_actions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "scope_classifications_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("granted_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.CheckConstraint(
            "state IN ('ACTIVE', 'SUSPENDED', 'ENDED', 'EXPIRED')",
            name="state",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(scope_actions_json) = 'array' "
            "AND jsonb_array_length(scope_actions_json) > 0",
            name="actions",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(scope_classifications_json) = 'array' "
            "AND jsonb_array_length(scope_classifications_json) > 0",
            name="classifications",
        ),
        sa.CheckConstraint("granted_at >= starts_at", name="granted_after_start"),
        sa.CheckConstraint("ends_at IS NULL OR ends_at > starts_at", name="end_after_start"),
        sa.CheckConstraint(
            "(state IN ('ACTIVE', 'SUSPENDED') AND ended_at IS NULL) OR "
            "(state IN ('ENDED', 'EXPIRED') AND ended_at IS NOT NULL)",
            name="state_timestamps",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_assignments__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_assignments__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_assignments__membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "granted_by_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_assignments__granted_by",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_case_assignments"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_assignments__tenant_id"),
    )
    op.create_index(
        "ix_case_assignments_tenant_id",
        "case_assignments",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_assignments__context_resolution",
        "case_assignments",
        ["tenant_id", "membership_id", "state", "starts_at", "ends_at"],
        unique=False,
    )
    op.create_index(
        "ux_assignments__active_member_case",
        "case_assignments",
        ["tenant_id", "membership_id", "case_id"],
        unique=True,
        postgresql_where=sa.text("state = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index("ux_assignments__active_member_case", table_name="case_assignments")
    op.drop_index("ix_assignments__context_resolution", table_name="case_assignments")
    op.drop_index("ix_case_assignments_tenant_id", table_name="case_assignments")
    op.drop_table("case_assignments")
    op.drop_constraint(
        "uq_memberships__tenant_id",
        "tenant_memberships",
        type_="unique",
    )
