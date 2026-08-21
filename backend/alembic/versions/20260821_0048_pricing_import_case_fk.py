"""Bind normalized pricing import batches to their tenant-scoped Case.

Revision ID: 20260821_0048
Revises: 20260818_0047
"""

from collections.abc import Sequence

from alembic import op

revision = "20260821_0048"
down_revision = "20260818_0047"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_pricing_import_batches__case",
        "pricing_import_batches",
        "cases",
        ["tenant_id", "case_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_pricing_import_batches__case",
        "pricing_import_batches",
        type_="foreignkey",
    )
