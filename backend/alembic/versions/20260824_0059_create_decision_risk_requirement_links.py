"""Create immutable links between risks and human-confirmed DCE requirements.

Revision ID: 20260824_0059
Revises: 20260824_0058
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260824_0059"
down_revision = "20260824_0058"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decision_risk_requirement_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("risk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requirement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dce_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("functional_key", sa.String(length=180), nullable=False),
        sa.Column("relationship", sa.String(length=16), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("source_refs_json", postgresql.JSONB(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_decision_risk_links__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_decision_risk_links__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "risk_id"],
            ["decision_risks.tenant_id", "decision_risks.id"],
            name="fk_decision_risk_links__risk",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "requirement_id"],
            ["dce_requirements.tenant_id", "dce_requirements.id"],
            name="fk_decision_risk_links__requirement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_decision_risk_links__dce_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_decision_risk_requirement_links"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_decision_risk_links__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "functional_key", name="uq_decision_risk_links__functional"
        ),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_decision_risk_links__command"),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_decision_risk_links__idempotency"
        ),
        sa.CheckConstraint(
            "relationship IN ('IMPACTS', 'MITIGATES', 'CONSTRAINS')",
            name="relationship",
        ),
        sa.CheckConstraint("char_length(btrim(rationale)) > 0", name="rationale_nonempty"),
    )
    op.create_index(
        "ix_decision_risk_links__tenant_case_created",
        "decision_risk_requirement_links",
        ["tenant_id", "case_id", "created_at"],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_decision_risk_link_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'DECISION_RISK_REQUIREMENT_LINK_APPEND_ONLY';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_decision_risk_links_append_only
        BEFORE UPDATE OR DELETE ON decision_risk_requirement_links
        FOR EACH ROW EXECUTE FUNCTION prevent_decision_risk_link_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_decision_risk_links_append_only "
        "ON decision_risk_requirement_links"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_decision_risk_link_mutation()")
    op.drop_index(
        "ix_decision_risk_links__tenant_case_created",
        table_name="decision_risk_requirement_links",
    )
    op.drop_table("decision_risk_requirement_links")
