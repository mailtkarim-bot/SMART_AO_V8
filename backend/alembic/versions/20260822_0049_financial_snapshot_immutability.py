"""Protect published financial snapshots from direct database mutation."""

from __future__ import annotations

from alembic import op

revision = "20260822_0049"
down_revision = "20260821_0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION prevent_published_financial_snapshot_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.state = 'PUBLISHED' THEN
                RAISE EXCEPTION 'published financial snapshots are immutable';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER financial_report_snapshots_published_immutable
        BEFORE UPDATE OR DELETE ON financial_report_snapshots
        FOR EACH ROW EXECUTE FUNCTION prevent_published_financial_snapshot_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS financial_report_snapshots_published_immutable
        ON financial_report_snapshots
        """
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_published_financial_snapshot_mutation()")
