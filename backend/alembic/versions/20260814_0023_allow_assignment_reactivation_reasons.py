"""Allow the closed patron reactivation reason catalogue in the append-only journal."""

from __future__ import annotations

from alembic import op

revision = "20260814_0023"
down_revision = "20260814_0022"
branch_labels = None
depends_on = None

_PREVIOUS_REASONS = (
    "'PATRON_SUSPENDED', 'WORKLOAD_REALLOCATION', 'CASE_PAUSED', 'ACCESS_REVIEW', "
    "'PATRON_ENDED', 'CASE_STOPPED', 'CASE_ARCHIVED', 'COLLABORATOR_UNAVAILABLE', "
    "'MEMBERSHIP_REVOKED'"
)
_REACTIVATION_REASONS = "'PATRON_REACTIVATED', 'CASE_RESUMED', 'ACCESS_REVIEW_CLEARED'"


def _reason_check(*, include_reactivation_reasons: bool) -> str:
    reasons = _PREVIOUS_REASONS
    if include_reactivation_reasons:
        reasons = f"{reasons}, {_REACTIVATION_REASONS}"
    return f"reason_code IS NULL OR reason_code IN ({reasons})"


def upgrade() -> None:
    op.drop_constraint(
        "reason",
        "case_assignment_change_events",
        type_="check",
    )
    op.create_check_constraint(
        "reason",
        "case_assignment_change_events",
        _reason_check(include_reactivation_reasons=True),
    )


def downgrade() -> None:
    op.drop_constraint(
        "reason",
        "case_assignment_change_events",
        type_="check",
    )
    op.create_check_constraint(
        "reason",
        "case_assignment_change_events",
        _reason_check(include_reactivation_reasons=False),
    )
