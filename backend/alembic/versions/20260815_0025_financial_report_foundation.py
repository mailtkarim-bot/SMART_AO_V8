"""Create immutable financial report snapshots and lines."""

# ruff: noqa: E501

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260815_0025"
down_revision = "20260815_0024"
branch_labels = None
depends_on = None

_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "financial_report_snapshots",
        sa.Column("id", _UUID, nullable=False), sa.Column("tenant_id", _UUID, nullable=False),
        sa.Column("case_id", _UUID, nullable=False), sa.Column("state", sa.String(16), nullable=False),
        sa.Column("currency_code", sa.CHAR(3), nullable=False), sa.Column("ruleset_version", sa.Integer, nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("sales_total_minor", sa.BigInteger, nullable=False), sa.Column("direct_cost_total_minor", sa.BigInteger, nullable=False),
        sa.Column("overhead_total_minor", sa.BigInteger, nullable=False), sa.Column("subcontracting_total_minor", sa.BigInteger, nullable=False),
        sa.Column("contingency_total_minor", sa.BigInteger, nullable=False), sa.Column("gross_margin_minor", sa.BigInteger, nullable=False),
        sa.Column("gross_margin_rate_bps", sa.Integer, nullable=False), sa.Column("forecast_cashflow_minor", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_financial_report_snapshots"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_financial_snapshot__tenant_id"),
        sa.CheckConstraint("state IN ('DRAFT', 'PUBLISHED')", name="state"), sa.CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name="currency"),
        sa.CheckConstraint("ruleset_version >= 1", name="ruleset_version"),
        sa.CheckConstraint("(state = 'DRAFT' AND published_at IS NULL) OR (state = 'PUBLISHED' AND published_at IS NOT NULL)", name="publication"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_financial_snapshot__tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "case_id"], ["cases.tenant_id", "cases.id"], name="fk_financial_snapshot__case", ondelete="RESTRICT"),
    )
    op.create_index("ix_financial_report_snapshots_tenant_id", "financial_report_snapshots", ["tenant_id"])
    op.create_index("ix_financial_snapshot__tenant_case", "financial_report_snapshots", ["tenant_id", "case_id", "created_at"])
    op.create_table(
        "financial_report_lines",
        sa.Column("id", _UUID, nullable=False), sa.Column("tenant_id", _UUID, nullable=False), sa.Column("snapshot_id", _UUID, nullable=False),
        sa.Column("category", sa.String(32), nullable=False), sa.Column("label", sa.String(160), nullable=False),
        sa.Column("quantity_decimal", sa.String(32), nullable=False), sa.Column("unit", sa.String(32), nullable=False), sa.Column("amount_minor", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_financial_report_lines"), sa.UniqueConstraint("tenant_id", "id", name="uq_financial_line__tenant_id"),
        sa.CheckConstraint("category IN ('SALES', 'DIRECT_COST', 'OVERHEAD', 'SUBCONTRACTING', 'CONTINGENCY', 'GROSS_MARGIN', 'FORECAST_CASHFLOW')", name="category"), sa.CheckConstraint("length(trim(label)) > 0", name="label"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_financial_line__tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "snapshot_id"], ["financial_report_snapshots.tenant_id", "financial_report_snapshots.id"], name="fk_financial_line__snapshot", ondelete="RESTRICT"),
    )
    op.create_index("ix_financial_report_lines_tenant_id", "financial_report_lines", ["tenant_id"])
    op.create_index("ix_financial_line__tenant_snapshot", "financial_report_lines", ["tenant_id", "snapshot_id", "created_at"])
    op.execute(
        "CREATE TRIGGER trg_financial_report_lines_append_only BEFORE UPDATE OR DELETE "
        "ON financial_report_lines FOR EACH ROW "
        "EXECUTE FUNCTION prevent_case_assignment_history_mutation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_financial_report_lines_append_only ON financial_report_lines")
    op.drop_table("financial_report_lines")
    op.drop_table("financial_report_snapshots")
