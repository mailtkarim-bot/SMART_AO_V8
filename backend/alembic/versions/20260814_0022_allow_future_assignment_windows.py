"""Allow contractually valid future Case assignment windows.

Revision ID: 20260814_0022
Revises: 20260814_0021
Create Date: 2026-08-14
"""

from __future__ import annotations

from alembic import op

revision = "20260814_0022"
down_revision = "20260814_0021"
branch_labels = None
depends_on = None

_WINDOW_CONSTRAINT = "granted_after_start"


def upgrade() -> None:
    """Remove only the historical check conflicting with the frozen state machine."""

    op.drop_constraint(_WINDOW_CONSTRAINT, "case_assignments", type_="check")


def downgrade() -> None:
    """Restore the former check only if no valid future window would be invalidated."""

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM case_assignments
                WHERE starts_at > granted_at
            ) THEN
                RAISE EXCEPTION
                    'cannot restore granted_after_start while future assignment windows exist';
            END IF;
        END $$;
        """
    )
    op.create_check_constraint(
        _WINDOW_CONSTRAINT,
        "case_assignments",
        "granted_at >= starts_at",
    )
