"""Create Case-scoped collaborator capability proposals and gaps.

Revision ID: 20260817_0034
Revises: 20260817_0033
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260817_0034"
down_revision = "20260817_0033"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _common_case_fks(prefix: str) -> tuple[sa.ForeignKeyConstraint, ...]:
    return (
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name=f"fk_{prefix}__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["case_assignments.tenant_id", "case_assignments.id"],
            name=f"fk_{prefix}__assignment",
            ondelete="RESTRICT",
        ),
    )


def upgrade() -> None:
    proposal_fks = _common_case_fks("case_capability_proposal") + (
        sa.ForeignKeyConstraint(
            ["tenant_id", "capability_id"],
            ["enterprise_capabilities.tenant_id", "enterprise_capabilities.id"],
            name="fk_case_capability_proposal__capability",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "capability_version_id"],
            ["enterprise_capability_versions.tenant_id", "enterprise_capability_versions.id"],
            name="fk_case_capability_proposal__version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "requirement_id"],
            ["dce_requirements.tenant_id", "dce_requirements.id"],
            name="fk_case_capability_proposal__requirement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["collaborator_tasks.tenant_id", "collaborator_tasks.id"],
            name="fk_case_capability_proposal__task",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "proposed_by_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_case_capability_proposal__membership",
            ondelete="RESTRICT",
        ),
    )
    op.create_table(
        "case_capability_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capability_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capability_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requirement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("state", sa.String(length=16), server_default="PROPOSED", nullable=False),
        sa.Column("validity_state", sa.String(length=16), nullable=False),
        sa.Column("justification", sa.String(length=2000), nullable=False),
        sa.Column("source_locator", sa.String(length=500), nullable=True),
        sa.Column("functional_key", sa.String(length=700), nullable=False),
        sa.Column("proposed_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        *proposal_fks,
        sa.PrimaryKeyConstraint("id", name="pk_case_capability_proposals"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_case_capability_proposal__tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_case_capability_proposal__command"),
        sa.UniqueConstraint(
            "tenant_id", "functional_key", name="uq_case_capability_proposal__functional"
        ),
        sa.CheckConstraint("state IN ('PROPOSED', 'TO_REVIEW')", name="state"),
        sa.CheckConstraint(
            "validity_state IN ('CURRENT', 'EXPIRED', 'UNKNOWN')", name="validity_state"
        ),
        sa.CheckConstraint(
            "requirement_id IS NOT NULL OR task_id IS NOT NULL", name="source_required"
        ),
    )
    op.create_index(
        "ix_case_capability_proposals_tenant_id", "case_capability_proposals", ["tenant_id"]
    )
    op.create_index(
        "ix_case_capability_proposals__tenant_case_state",
        "case_capability_proposals",
        ["tenant_id", "case_id", "state", "created_at"],
    )

    gap_fks = _common_case_fks("case_capability_gap") + (
        sa.ForeignKeyConstraint(
            ["tenant_id", "capability_id"],
            ["enterprise_capabilities.tenant_id", "enterprise_capabilities.id"],
            name="fk_case_capability_gap__capability",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "requirement_id"],
            ["dce_requirements.tenant_id", "dce_requirements.id"],
            name="fk_case_capability_gap__requirement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["collaborator_tasks.tenant_id", "collaborator_tasks.id"],
            name="fk_case_capability_gap__task",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "reported_by_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_case_capability_gap__membership",
            ondelete="RESTRICT",
        ),
    )
    op.create_table(
        "case_capability_gaps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capability_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requirement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("gap_kind", sa.String(length=16), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=2000), nullable=False),
        sa.Column("source_locator", sa.String(length=500), nullable=True),
        sa.Column("recommended_action", sa.String(length=1000), nullable=False),
        sa.Column("functional_key", sa.String(length=700), nullable=False),
        sa.Column("reported_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        *gap_fks,
        sa.PrimaryKeyConstraint("id", name="pk_case_capability_gaps"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_case_capability_gap__tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_case_capability_gap__command"),
        sa.UniqueConstraint(
            "tenant_id", "functional_key", name="uq_case_capability_gap__functional"
        ),
        sa.CheckConstraint(
            "gap_kind IN ('MISSING', 'EXPIRED', 'UNAUTHORIZED', 'INSUFFICIENT')", name="gap_kind"
        ),
        sa.CheckConstraint(
            "severity IN ('INFORMATIONAL', 'IMPORTANT', 'BLOCKING')", name="severity"
        ),
        sa.CheckConstraint(
            "requirement_id IS NOT NULL OR task_id IS NOT NULL", name="source_required"
        ),
    )
    op.create_index("ix_case_capability_gaps_tenant_id", "case_capability_gaps", ["tenant_id"])
    op.create_index(
        "ix_case_capability_gaps__tenant_case_severity",
        "case_capability_gaps",
        ["tenant_id", "case_id", "severity", "created_at"],
    )

    for table, function, trigger, message in (
        (
            "case_capability_proposals",
            "prevent_case_capability_proposal_mutation",
            "case_capability_proposals_append_only",
            "case capability proposals are append-only",
        ),
        (
            "case_capability_gaps",
            "prevent_case_capability_gap_mutation",
            "case_capability_gaps_append_only",
            "case capability gaps are append-only",
        ),
    ):
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


def downgrade() -> None:
    for table, function, trigger in (
        (
            "case_capability_gaps",
            "prevent_case_capability_gap_mutation",
            "case_capability_gaps_append_only",
        ),
        (
            "case_capability_proposals",
            "prevent_case_capability_proposal_mutation",
            "case_capability_proposals_append_only",
        ),
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS {function}()")
    op.execute("DROP INDEX IF EXISTS ix_case_capability_gaps__tenant_case_severity")
    op.execute("DROP INDEX IF EXISTS ix_case_capability_gaps_tenant_id")
    op.drop_table("case_capability_gaps")
    op.execute("DROP INDEX IF EXISTS ix_case_capability_proposals__tenant_case_state")
    op.execute("DROP INDEX IF EXISTS ix_case_capability_proposals_tenant_id")
    op.drop_table("case_capability_proposals")
