from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.platform.persistence.repository import (
    OptimisticRevisionConflictError,
    update_root_with_expected_revision,
)


@pytest.fixture
def aggregate_table() -> sa.Table:
    return sa.table(
        "aggregate_root",
        sa.column("tenant_id"),
        sa.column("id"),
        sa.column("aggregate_revision"),
        sa.column("state"),
        sa.column("updated_at"),
    )


class RecordingSession:
    def __init__(self, *, rowcount: int) -> None:
        self.rowcount = rowcount
        self.statement = None

    def execute(self, statement):
        self.statement = statement
        return SimpleNamespace(rowcount=self.rowcount)


def test_update_root_rejects_negative_revision(aggregate_table: sa.Table) -> None:
    with pytest.raises(ValueError, match="expected_revision must be non-negative"):
        update_root_with_expected_revision(
            RecordingSession(rowcount=1),
            table=aggregate_table,
            tenant_id=uuid4(),
            aggregate_id=uuid4(),
            expected_revision=-1,
            changes={"state": "READY"},
            allowed_columns=frozenset({"state"}),
        )


def test_update_root_rejects_empty_and_forbidden_changes(aggregate_table: sa.Table) -> None:
    session = RecordingSession(rowcount=1)
    common = {
        "session": session,
        "table": aggregate_table,
        "tenant_id": uuid4(),
        "aggregate_id": uuid4(),
        "expected_revision": 0,
        "allowed_columns": frozenset({"state"}),
    }
    with pytest.raises(ValueError, match="at least one change"):
        update_root_with_expected_revision(changes={}, **common)
    with pytest.raises(ValueError, match="forbidden columns: other, status"):
        update_root_with_expected_revision(
            changes={"status": "OPEN", "other": "value"}, **common
        )
    assert session.statement is None


def test_update_root_returns_next_revision_and_records_statement(
    aggregate_table: sa.Table,
) -> None:
    session = RecordingSession(rowcount=1)
    next_revision = update_root_with_expected_revision(
        session,
        table=aggregate_table,
        tenant_id=uuid4(),
        aggregate_id=uuid4(),
        expected_revision=4,
        changes={"state": "READY"},
        allowed_columns=frozenset({"state"}),
    )

    assert next_revision == 5
    assert session.statement is not None
    assert "aggregate_revision" in str(session.statement)
    assert "updated_at" in str(session.statement)


def test_update_root_maps_zero_rowcount_to_optimistic_conflict(
    aggregate_table: sa.Table,
) -> None:
    with pytest.raises(OptimisticRevisionConflictError, match="changed or is unavailable"):
        update_root_with_expected_revision(
            RecordingSession(rowcount=0),
            table=aggregate_table,
            tenant_id=uuid4(),
            aggregate_id=uuid4(),
            expected_revision=0,
            changes={"state": "READY"},
            allowed_columns=frozenset({"state"}),
        )


def test_update_root_maps_multiple_rows_to_optimistic_conflict(
    aggregate_table: sa.Table,
) -> None:
    with pytest.raises(OptimisticRevisionConflictError):
        update_root_with_expected_revision(
            RecordingSession(rowcount=2),
            table=aggregate_table,
            tenant_id=uuid4(),
            aggregate_id=uuid4(),
            expected_revision=0,
            changes={"state": "READY"},
            allowed_columns=frozenset({"state"}),
        )
