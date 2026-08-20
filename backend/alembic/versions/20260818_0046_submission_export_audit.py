"""Allow dedicated immutable audit events for submission package exports.

Revision ID: 20260818_0046
Revises: 20260818_0045
Create Date: 2026-08-18
"""

from __future__ import annotations

from alembic import op

revision = "20260818_0046"
down_revision = "20260818_0045"
branch_labels = None
depends_on = None

_EVENT_TYPE_CONSTRAINT = (
    "event_type IN ("
    "'AUTH_LOGIN_SUCCEEDED', 'AUTH_LOGIN_DENIED', "
    "'AUTH_REFRESH_SUCCEEDED', 'AUTH_REFRESH_DENIED', "
    "'AUTH_LOGOUT_SUCCEEDED', 'AUTH_SESSION_REJECTED', "
    "'AUTHZ_SUCCEEDED', 'AUTHZ_DENIED', 'AUTHZ_STEP_UP_REQUIRED', "
    "'SUBMISSION_PACKAGE_EXPORTED'"
    ")"
)
_PREVIOUS_EVENT_TYPE_CONSTRAINT = (
    "event_type IN ("
    "'AUTH_LOGIN_SUCCEEDED', 'AUTH_LOGIN_DENIED', "
    "'AUTH_REFRESH_SUCCEEDED', 'AUTH_REFRESH_DENIED', "
    "'AUTH_LOGOUT_SUCCEEDED', 'AUTH_SESSION_REJECTED', "
    "'AUTHZ_SUCCEEDED', 'AUTHZ_DENIED', 'AUTHZ_STEP_UP_REQUIRED'"
    ")"
)


def upgrade() -> None:
    op.drop_constraint(
        "event_type",
        "security_audit_events",
        type_="check",
    )
    op.create_check_constraint(
        "event_type",
        "security_audit_events",
        _EVENT_TYPE_CONSTRAINT,
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE security_audit_events DISABLE TRIGGER trg_security_audit_append_only"
    )
    op.execute(
        "DELETE FROM security_audit_events WHERE event_type = 'SUBMISSION_PACKAGE_EXPORTED'"
    )
    op.execute(
        "ALTER TABLE security_audit_events ENABLE TRIGGER trg_security_audit_append_only"
    )
    op.drop_constraint(
        "event_type",
        "security_audit_events",
        type_="check",
    )
    op.create_check_constraint(
        "event_type",
        "security_audit_events",
        _PREVIOUS_EVENT_TYPE_CONSTRAINT,
    )
