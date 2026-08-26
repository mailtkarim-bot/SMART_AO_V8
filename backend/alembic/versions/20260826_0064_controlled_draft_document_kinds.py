"""Allow controlled DC1/DC2/DC4 document kinds.

Revision ID: 20260826_0064
Revises: 20260825_0063
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260826_0064"
down_revision = "20260825_0063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "generated_technical_documents"
_CONSTRAINT = "document_kind"
_ALLOWED = "document_kind IN ('TECHNICAL_RESPONSE', 'DC1', 'DC2', 'DC4')"
_LEGACY = "document_kind IN ('TECHNICAL_RESPONSE')"


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT, _TABLE, type_="check")
    op.create_check_constraint(_CONSTRAINT, _TABLE, _ALLOWED)


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, _TABLE, type_="check")
    # Existing DC rows are legitimate under this revision. Restore the legacy
    # contract as NOT VALID so downgrade does not delete data or fail halfway;
    # PostgreSQL still enforces the legacy rule for new rows.
    op.execute(
        sa.text(
            "ALTER TABLE generated_technical_documents ADD CONSTRAINT document_kind "
            "CHECK (document_kind IN ('TECHNICAL_RESPONSE')) NOT VALID"
        )
    )
