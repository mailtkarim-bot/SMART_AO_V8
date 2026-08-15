"""Add immutable patron publication acts for financial report snapshots.

Revision ID: 20260816_0026
Revises: 20260815_0025
"""

import sqlalchemy as sa
from alembic import op

revision = "20260816_0026"
down_revision = "20260815_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "financial_report_snapshots",
        sa.Column("aggregate_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "financial_report_publications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("patron_membership_id", sa.Uuid(), nullable=False),
        sa.Column("command_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
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
            ["tenant_id", "snapshot_id"],
            ["financial_report_snapshots.tenant_id", "financial_report_snapshots.id"],
            name="fk_financial_publication__snapshot",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "patron_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_financial_publication__patron",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "snapshot_id", name="uq_financial_publication__snapshot"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_financial_publication__command"),
    )
    op.create_index(
        "ix_financial_publication__tenant_snapshot",
        "financial_report_publications",
        ["tenant_id", "snapshot_id"],
    )
    op.create_index(
        "ix_financial_report_publications_tenant_id",
        "financial_report_publications",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_financial_report_publications_tenant_id")
    op.drop_index(
        "ix_financial_publication__tenant_snapshot",
        table_name="financial_report_publications",
    )
    op.drop_table("financial_report_publications")
    op.drop_column("financial_report_snapshots", "aggregate_revision")
