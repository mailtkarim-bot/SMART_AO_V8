"""Expose an honest NOT_CONFIGURED terminal state for optional integrations.

Revision ID: 20260825_0061
Revises: 20260825_0060

Workers for optional integrations (SMTP notification, export webhook) must stop
masking a missing configuration as a successful PUBLISHED delivery. This
migration widens the outbox status vocabulary with NOT_CONFIGURED so an absent,
voluntarily disabled integration is visible and alertable instead of being
recorded as success.
"""

from collections.abc import Sequence

from alembic import op

revision = "20260825_0061"
down_revision = "20260825_0060"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE outbox_messages DROP CONSTRAINT ck_outbox_messages__status")
    op.create_check_constraint(
        "status",
        "outbox_messages",
        "status IN ('PENDING', 'PUBLISHED', 'RETRY', 'FAILED', 'NOT_CONFIGURED')",
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE outbox_messages
        SET status = 'FAILED',
            last_error_code = 'INTEGRATION_NOT_CONFIGURED'
        WHERE status = 'NOT_CONFIGURED'
        """
    )
    op.execute("ALTER TABLE outbox_messages DROP CONSTRAINT ck_outbox_messages__status")
    op.create_check_constraint(
        "status",
        "outbox_messages",
        "status IN ('PENDING', 'PUBLISHED', 'RETRY', 'FAILED')",
    )
