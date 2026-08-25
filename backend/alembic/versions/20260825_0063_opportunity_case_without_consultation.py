"""Allow qualified opportunity Cases without a Consultation reference.

Revision ID: 20260825_0063
Revises: 20260825_0062
"""

from collections.abc import Sequence

from alembic import op

revision = "20260825_0063"
down_revision = "20260825_0062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT = "consultation_required_unless_manual"


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "cases", type_="check")
    op.create_check_constraint(
        _CONSTRAINT,
        "cases",
        "consultation_id IS NOT NULL OR business_origin = 'MANUAL' OR "
        "(business_origin = 'OPPORTUNITY' AND origin_reference_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "cases", type_="check")
    op.create_check_constraint(
        _CONSTRAINT,
        "cases",
        "consultation_id IS NOT NULL OR business_origin = 'MANUAL'",
    )
