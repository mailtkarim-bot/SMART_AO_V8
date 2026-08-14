"""Allow successful authorization events in the SEC-01 audit registry.

Revision ID: 20260814_0018
Revises: 20260814_0017
Create Date: 2026-08-14
"""

from __future__ import annotations

from alembic import op

revision = "20260814_0018"
down_revision = "20260814_0017"
branch_labels = None
depends_on = None

_EVENT_TYPE_CONSTRAINT = (
    "event_type IN ("
    "'AUTH_LOGIN_SUCCEEDED', 'AUTH_LOGIN_DENIED', "
    "'AUTH_REFRESH_SUCCEEDED', 'AUTH_REFRESH_DENIED', "
    "'AUTH_LOGOUT_SUCCEEDED', 'AUTH_SESSION_REJECTED', "
    "'AUTHZ_SUCCEEDED', 'AUTHZ_DENIED', 'AUTHZ_STEP_UP_REQUIRED'"
    ")"
)
_PREVIOUS_EVENT_TYPE_CONSTRAINT = (
    "event_type IN ("
    "'AUTH_LOGIN_SUCCEEDED', 'AUTH_LOGIN_DENIED', "
    "'AUTH_REFRESH_SUCCEEDED', 'AUTH_REFRESH_DENIED', "
    "'AUTH_LOGOUT_SUCCEEDED', 'AUTH_SESSION_REJECTED', "
    "'AUTHZ_DENIED', 'AUTHZ_STEP_UP_REQUIRED'"
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
