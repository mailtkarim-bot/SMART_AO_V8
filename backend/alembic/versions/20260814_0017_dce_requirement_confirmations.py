"""Create immutable DCE requirement human confirmation registry.

Revision ID: 20260814_0017
Revises: 20260814_0016
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260814_0017"
down_revision = "20260814_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "dce_requirement_confirmations",
        sa.Column("id", uuid, nullable=False),
        sa.Column("tenant_id", uuid, nullable=False),
        sa.Column("requirement_id", uuid, nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("previous_confirmation_id", uuid, nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("confirmed_by_actor_id", uuid, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_dce_req_conf__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "requirement_id"],
            ["dce_requirements.tenant_id", "dce_requirements.id"],
            name="fk_dce_req_conf__requirement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "previous_confirmation_id"],
            ["dce_requirement_confirmations.tenant_id", "dce_requirement_confirmations.id"],
            name="fk_dce_req_conf__previous",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dce_requirement_confirmations"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_req_conf__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "requirement_id", "revision", name="uq_dce_req_conf_revision"
        ),
        sa.CheckConstraint("revision > 0", name="revision_positive"),
        sa.CheckConstraint(
            "outcome IN ('CONFIRMED', 'REVIEW_REQUIRED', 'NOT_APPLICABLE')", name="outcome"
        ),
        sa.CheckConstraint(
            "reason_code IN ('SOURCE_REVIEWED', 'AMBIGUOUS_SOURCE', "
            "'CONTRADICTORY_DCE', 'PATRON_NOT_APPLICABLE', "
            "'NEEDS_EXTERNAL_CLARIFICATION')",
            name="reason",
        ),
    )
    op.create_index(
        "ix_dce_req_conf__tenant_requirement_revision",
        "dce_requirement_confirmations",
        ["tenant_id", "requirement_id", "revision"],
    )
    op.create_index(
        "ix_dce_requirement_confirmations_tenant_id", "dce_requirement_confirmations", ["tenant_id"]
    )
    op.create_table(
        "dce_requirement_confirmation_current",
        sa.Column("requirement_id", uuid, nullable=False),
        sa.Column("tenant_id", uuid, nullable=False),
        sa.Column("confirmation_id", uuid, nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_dce_req_conf_cur__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "requirement_id"],
            ["dce_requirements.tenant_id", "dce_requirements.id"],
            name="fk_dce_req_conf_cur__requirement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "confirmation_id"],
            ["dce_requirement_confirmations.tenant_id", "dce_requirement_confirmations.id"],
            name="fk_dce_req_conf_cur__confirmation",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("requirement_id", name="pk_dce_requirement_confirmation_current"),
        sa.UniqueConstraint("tenant_id", "requirement_id", name="uq_dce_req_conf_cur_requirement"),
        sa.CheckConstraint("revision > 0", name="revision_positive"),
        sa.CheckConstraint(
            "outcome IN ('CONFIRMED', 'REVIEW_REQUIRED', 'NOT_APPLICABLE')", name="outcome"
        ),
    )
    op.create_index(
        "ix_dce_requirement_confirmation_current_tenant_id",
        "dce_requirement_confirmation_current",
        ["tenant_id"],
    )
    op.execute(
        "CREATE FUNCTION prevent_dce_requirement_confirmation_mutation() RETURNS trigger AS $$ "
        "BEGIN RAISE EXCEPTION 'DCE_REQUIREMENT_CONFIRMATION_APPEND_ONLY'; "
        "END; $$ LANGUAGE plpgsql;"
    )
    op.execute(
        "CREATE TRIGGER trg_dce_req_conf_append_only BEFORE UPDATE OR DELETE ON "
        "dce_requirement_confirmations FOR EACH ROW EXECUTE FUNCTION "
        "prevent_dce_requirement_confirmation_mutation()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_dce_req_conf_append_only ON dce_requirement_confirmations"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_dce_requirement_confirmation_mutation()")
    op.drop_index(
        "ix_dce_requirement_confirmation_current_tenant_id",
        table_name="dce_requirement_confirmation_current",
    )
    op.drop_table("dce_requirement_confirmation_current")
    op.drop_index(
        "ix_dce_requirement_confirmations_tenant_id", table_name="dce_requirement_confirmations"
    )
    op.drop_index(
        "ix_dce_req_conf__tenant_requirement_revision", table_name="dce_requirement_confirmations"
    )
    op.drop_table("dce_requirement_confirmations")
