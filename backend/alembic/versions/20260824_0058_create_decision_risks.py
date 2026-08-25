"""Create immutable structured CCAP/CCTP decision risks.

Revision ID: 20260824_0058
Revises: 20260824_0057
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260824_0058"
down_revision = "20260824_0057"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decision_risks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dce_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_fragment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("functional_key", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("risk_code", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("likelihood", sa.String(length=20), nullable=False),
        sa.Column("treatment", sa.String(length=16), server_default="OPEN", nullable=False),
        sa.Column("source_excerpt", sa.String(length=2000), nullable=False),
        sa.Column("source_locator_json", postgresql.JSONB(), nullable=False),
        sa.Column("start_byte_offset", sa.Integer(), nullable=False),
        sa.Column("end_byte_offset", sa.Integer(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_decision_risks__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_decision_risks__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_decision_risks__dce_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "source_fragment_id"],
            ["dce_document_extraction_fragments.tenant_id", "dce_document_extraction_fragments.id"],
            name="fk_decision_risks__source_fragment",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_decision_risks"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_decision_risks__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "functional_key", name="uq_decision_risks__functional_key"
        ),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_decision_risks__command_id"),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_decision_risks__idempotency_key"
        ),
        sa.CheckConstraint("category IN ('CCAP', 'CCTP')", name="category"),
        sa.CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name="severity"
        ),
        sa.CheckConstraint(
            "likelihood IN ('RARE', 'POSSIBLE', 'LIKELY', 'ALMOST_CERTAIN')", name="likelihood"
        ),
        sa.CheckConstraint("treatment IN ('OPEN', 'ACCEPTED', 'MITIGATED')", name="treatment"),
        sa.CheckConstraint("char_length(btrim(title)) > 0", name="title_nonempty"),
        sa.CheckConstraint("char_length(btrim(statement)) > 0", name="statement_nonempty"),
        sa.CheckConstraint(
            "char_length(btrim(source_excerpt)) > 0", name="source_excerpt_nonempty"
        ),
        sa.CheckConstraint("start_byte_offset >= 0", name="start_offset_nonnegative"),
        sa.CheckConstraint("end_byte_offset > start_byte_offset", name="offsets_ordered"),
    )
    op.create_index(
        "ix_decision_risks__tenant_case", "decision_risks", ["tenant_id", "case_id", "created_at"]
    )
    op.execute(
        """
        CREATE FUNCTION prevent_decision_risk_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'DECISION_RISK_APPEND_ONLY';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_decision_risks_append_only
        BEFORE UPDATE OR DELETE ON decision_risks
        FOR EACH ROW EXECUTE FUNCTION prevent_decision_risk_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_decision_risks_append_only ON decision_risks")
    op.execute("DROP FUNCTION IF EXISTS prevent_decision_risk_mutation()")
    op.drop_index("ix_decision_risks__tenant_case", table_name="decision_risks")
    op.drop_table("decision_risks")
