"""Allow only current-state projection updates on patron actions.

Revision ID: 20260824_0056
Revises: 20260823_0055
"""

from collections.abc import Sequence

from alembic import op

revision = "20260824_0056"
down_revision = "20260823_0055"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


_STRICT_FUNCTION = """
CREATE FUNCTION prevent_patron_action_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'patron actions are append-only';
END;
$$;
"""

_PROJECTION_FUNCTION = """
CREATE FUNCTION prevent_patron_action_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF OLD.id IS DISTINCT FROM NEW.id
        OR OLD.tenant_id IS DISTINCT FROM NEW.tenant_id
        OR OLD.created_at IS DISTINCT FROM NEW.created_at
        OR OLD.case_id IS DISTINCT FROM NEW.case_id
        OR OLD.functional_key IS DISTINCT FROM NEW.functional_key
        OR OLD.action_type IS DISTINCT FROM NEW.action_type
        OR OLD.severity IS DISTINCT FROM NEW.severity
        OR OLD.title IS DISTINCT FROM NEW.title
        OR OLD.why_now IS DISTINCT FROM NEW.why_now
        OR OLD.impact IS DISTINCT FROM NEW.impact
        OR OLD.recommended_action IS DISTINCT FROM NEW.recommended_action
        OR OLD.due_at IS DISTINCT FROM NEW.due_at
        OR OLD.source_refs_json IS DISTINCT FROM NEW.source_refs_json
        OR OLD.actor_id IS DISTINCT FROM NEW.actor_id
        OR OLD.membership_id IS DISTINCT FROM NEW.membership_id
        OR OLD.command_id IS DISTINCT FROM NEW.command_id
        OR OLD.idempotency_key IS DISTINCT FROM NEW.idempotency_key
        OR OLD.correlation_id IS DISTINCT FROM NEW.correlation_id
        THEN
            RAISE EXCEPTION 'patron actions are append-only';
        END IF;
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'patron actions are append-only';
END;
$$;
"""


def _drop_guard() -> None:
    op.execute("DROP TRIGGER IF EXISTS patron_actions_append_only ON patron_actions")
    op.execute("DROP FUNCTION IF EXISTS prevent_patron_action_mutation()")


def _create_guard(function_sql: str) -> None:
    op.execute(function_sql)
    op.execute(
        """
        CREATE TRIGGER patron_actions_append_only
        BEFORE UPDATE OR DELETE ON patron_actions
        FOR EACH ROW EXECUTE FUNCTION prevent_patron_action_mutation();
        """
    )


def upgrade() -> None:
    _drop_guard()
    _create_guard(_PROJECTION_FUNCTION)


def downgrade() -> None:
    _drop_guard()
    _create_guard(_STRICT_FUNCTION)
