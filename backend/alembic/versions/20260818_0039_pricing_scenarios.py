"""Create private pricing scenarios.

Revision ID: 20260818_0039
Revises: 20260818_0038
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260818_0039"
down_revision = "20260818_0038"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pricing_scenarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scenario_key", sa.String(length=120), nullable=False),
        sa.Column("scenario_type", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("assumptions_json", postgresql.JSONB, nullable=False),
        sa.Column("sales_total_minor", sa.BigInteger, nullable=False),
        sa.Column("total_cost_minor", sa.BigInteger, nullable=False),
        sa.Column("gross_margin_minor", sa.BigInteger, nullable=False),
        sa.Column("gross_margin_rate_bps", sa.Integer, nullable=False),
        sa.Column("source_snapshot_revision", sa.Integer, nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_pricing_scenarios"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_pricing_scenarios__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "source_snapshot_id"],
            ["financial_report_snapshots.tenant_id", "financial_report_snapshots.id"],
            name="fk_pricing_scenarios__snapshot",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_pricing_scenarios__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "case_id",
            "scenario_key",
            "version",
            name="uq_pricing_scenario_version",
        ),
        sa.CheckConstraint("version > 0", name="version_positive"),
        sa.CheckConstraint("state IN ('DRAFT', 'SELECTED', 'ARCHIVED')", name="state"),
        sa.CheckConstraint(
            "scenario_type IN ('BASE', 'PRUDENT', 'CUSTOM')", name="scenario_type"
        ),
    )
    op.create_index("ix_pricing_scenarios_tenant_id", "pricing_scenarios", ["tenant_id"])
    op.create_index(
        "ix_pricing_scenarios__tenant_case",
        "pricing_scenarios",
        ["tenant_id", "case_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_pricing_scenarios__tenant_case", table_name="pricing_scenarios")
    op.drop_index("ix_pricing_scenarios_tenant_id", table_name="pricing_scenarios")
    op.drop_table("pricing_scenarios")
