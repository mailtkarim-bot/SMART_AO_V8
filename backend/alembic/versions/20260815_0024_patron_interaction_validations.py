"""Create immutable patron validations for collaborator assignment interactions."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260815_0024"
down_revision = "20260814_0023"
branch_labels = None
depends_on = None

_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "assignment_interaction_patron_validations",
        sa.Column("id", _UUID, nullable=False),
        sa.Column("tenant_id", _UUID, nullable=False),
        sa.Column("assignment_id", _UUID, nullable=False),
        sa.Column("case_id", _UUID, nullable=False),
        sa.Column("interaction_id", _UUID, nullable=False),
        sa.Column("interaction_kind", sa.String(32), nullable=False),
        sa.Column("validation_code", sa.String(32), nullable=False),
        sa.Column("patron_membership_id", _UUID, nullable=False),
        sa.Column("command_id", _UUID, nullable=False),
        sa.Column("correlation_id", _UUID, nullable=True),
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
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_assignment_interaction_validation__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["case_assignments.tenant_id", "case_assignments.id"],
            name="fk_assignment_interaction_validation__assignment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_assignment_interaction_validation__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "patron_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_assignment_interaction_validation__patron",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assignment_interaction_patron_validations"),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_assignment_interaction_validation__tenant_id",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "interaction_kind",
            "interaction_id",
            name="uq_assignment_interaction_validation__source",
        ),
        sa.CheckConstraint(
            "interaction_kind IN "
            "('ACKNOWLEDGEMENT', 'CLARIFICATION_REQUEST', 'UNAVAILABILITY_REPORT')",
            name="interaction_kind",
        ),
        sa.CheckConstraint(
            "validation_code IN "
            "('ACKNOWLEDGEMENT_NOTED', 'CLARIFICATION_NOTED', 'UNAVAILABILITY_NOTED') "
            "AND ((interaction_kind = 'ACKNOWLEDGEMENT' "
            "AND validation_code = 'ACKNOWLEDGEMENT_NOTED') "
            "OR (interaction_kind = 'CLARIFICATION_REQUEST' "
            "AND validation_code = 'CLARIFICATION_NOTED') "
            "OR (interaction_kind = 'UNAVAILABILITY_REPORT' "
            "AND validation_code = 'UNAVAILABILITY_NOTED'))",
            name="kind_code",
        ),
    )
    op.create_index(
        "ix_assignment_interaction_validation__tenant_assignment",
        "assignment_interaction_patron_validations",
        ["tenant_id", "assignment_id", "created_at"],
    )
    op.create_index(
        "ix_assignment_interaction_patron_validations_tenant_id",
        "assignment_interaction_patron_validations",
        ["tenant_id"],
    )
    op.execute(
        "CREATE TRIGGER trg_assignment_interaction_patron_validations_append_only "
        "BEFORE UPDATE OR DELETE ON assignment_interaction_patron_validations "
        "FOR EACH ROW EXECUTE FUNCTION prevent_case_assignment_history_mutation()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_assignment_interaction_patron_validations_append_only "
        "ON assignment_interaction_patron_validations"
    )
    op.drop_index(
        "ix_assignment_interaction_validation__tenant_assignment",
        table_name="assignment_interaction_patron_validations",
    )
    op.execute(
        "DROP INDEX IF EXISTS ix_assignment_interaction_patron_validations_tenant_id"
    )
    op.drop_table("assignment_interaction_patron_validations")
