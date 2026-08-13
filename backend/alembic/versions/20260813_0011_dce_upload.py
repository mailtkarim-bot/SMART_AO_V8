"""Add DCE-UPLOAD-01 staging upload state.

Revision ID: 20260813_0011
Revises: 20260813_0010
Create Date: 2026-08-13
"""

from __future__ import annotations

from alembic import op

revision = "20260813_0011"
down_revision = "20260813_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("state", "dce_staged_objects", type_="check")
    op.create_check_constraint(
        "state",
        "dce_staged_objects",
        "state IN ('AWAITING_UPLOAD', 'UPLOADING', 'QUARANTINED', 'CLEAN', "
        "'REJECTED', 'CONSUMED', 'EXPIRED')",
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_dce_staged_object_transition() RETURNS trigger AS $$
        BEGIN
          IF OLD.state = 'AWAITING_UPLOAD'
             AND NEW.state IN ('UPLOADING', 'REJECTED', 'EXPIRED') THEN
            RETURN NEW;
          ELSIF OLD.state = 'UPLOADING'
             AND NEW.state IN ('QUARANTINED', 'REJECTED', 'EXPIRED') THEN
            RETURN NEW;
          ELSIF OLD.state = 'QUARANTINED'
             AND NEW.state IN ('CLEAN', 'REJECTED', 'EXPIRED') THEN
            RETURN NEW;
          ELSIF OLD.state = 'CLEAN'
             AND NEW.state IN ('CONSUMED', 'EXPIRED') THEN
            RETURN NEW;
          ELSIF OLD.state = 'REJECTED' AND NEW.state = 'EXPIRED' THEN
            RETURN NEW;
          END IF;
          RAISE EXCEPTION 'DCE_STAGED_OBJECT_INVALID_TRANSITION';
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_dce_staged_object_transition() RETURNS trigger AS $$
        BEGIN
          IF OLD.state = 'AWAITING_UPLOAD'
             AND NEW.state IN ('QUARANTINED', 'REJECTED', 'EXPIRED') THEN
            RETURN NEW;
          ELSIF OLD.state = 'QUARANTINED'
             AND NEW.state IN ('CLEAN', 'REJECTED', 'EXPIRED') THEN
            RETURN NEW;
          ELSIF OLD.state = 'CLEAN'
             AND NEW.state IN ('CONSUMED', 'EXPIRED') THEN
            RETURN NEW;
          ELSIF OLD.state = 'REJECTED' AND NEW.state = 'EXPIRED' THEN
            RETURN NEW;
          END IF;
          RAISE EXCEPTION 'DCE_STAGED_OBJECT_INVALID_TRANSITION';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.drop_constraint("state", "dce_staged_objects", type_="check")
    op.create_check_constraint(
        "state",
        "dce_staged_objects",
        "state IN ('AWAITING_UPLOAD', 'QUARANTINED', 'CLEAN', 'REJECTED', "
        "'CONSUMED', 'EXPIRED')",
    )
