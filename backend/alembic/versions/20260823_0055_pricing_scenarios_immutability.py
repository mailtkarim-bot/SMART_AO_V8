"""Protect pricing scenarios from direct database mutation."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision = "20260823_0055"
down_revision = "20260823_0054"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION prevent_pricing_scenario_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'pricing scenarios are immutable; use pricing scenario transitions';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER pricing_scenarios_append_only
        BEFORE UPDATE OR DELETE ON pricing_scenarios
        FOR EACH ROW EXECUTE FUNCTION prevent_pricing_scenario_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS pricing_scenarios_append_only
        ON pricing_scenarios
        """
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_pricing_scenario_mutation()")
