"""Allow normalized import rows to retain validation errors.

Revision ID: 20260818_0044
Revises: 20260818_0043
"""

from collections.abc import Sequence

from alembic import op

revision = "20260818_0044"
down_revision = "20260818_0043"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("pricing_import_rows", "designation", nullable=True)
    op.alter_column("pricing_import_rows", "quantity_decimal", nullable=True)
    op.alter_column("pricing_import_rows", "unit_price_minor", nullable=True)
    op.alter_column("pricing_import_rows", "total_minor", nullable=True)
    op.drop_constraint("designation", "pricing_import_rows", type_="check")
    op.drop_constraint("quantity_decimal_non_empty", "pricing_import_rows", type_="check")
    op.drop_constraint("unit_price_non_negative", "pricing_import_rows", type_="check")
    op.drop_constraint("total_non_negative", "pricing_import_rows", type_="check")
    op.create_check_constraint(
        "designation",
        "pricing_import_rows",
        "designation IS NULL OR length(trim(designation)) > 0",
    )
    op.create_check_constraint(
        "quantity_decimal_non_empty",
        "pricing_import_rows",
        "quantity_decimal IS NULL OR quantity_decimal <> ''",
    )
    op.create_check_constraint(
        "unit_price_non_negative",
        "pricing_import_rows",
        "unit_price_minor IS NULL OR unit_price_minor >= 0",
    )
    op.create_check_constraint(
        "total_non_negative",
        "pricing_import_rows",
        "total_minor IS NULL OR total_minor >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("designation", "pricing_import_rows", type_="check")
    op.drop_constraint("quantity_decimal_non_empty", "pricing_import_rows", type_="check")
    op.drop_constraint("unit_price_non_negative", "pricing_import_rows", type_="check")
    op.drop_constraint("total_non_negative", "pricing_import_rows", type_="check")
    op.create_check_constraint(
        "designation", "pricing_import_rows", "length(trim(designation)) > 0"
    )
    op.create_check_constraint(
        "quantity_decimal_non_empty", "pricing_import_rows", "quantity_decimal <> ''"
    )
    op.create_check_constraint(
        "unit_price_non_negative", "pricing_import_rows", "unit_price_minor >= 0"
    )
    op.create_check_constraint("total_non_negative", "pricing_import_rows", "total_minor >= 0")
    # A PREVIEWED row may legitimately retain validation errors and NULL values.
    # Tightening these columns would make a downgrade fail or destroy append-only data.
