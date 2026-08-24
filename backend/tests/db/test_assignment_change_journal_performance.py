from importlib.util import module_from_spec, spec_from_file_location

import pytest
import sqlalchemy as sa
from tests.support.database import REPOSITORY_ROOT

MAX_INSERT_MILLISECONDS = 5_000
MAX_RECENT_READ_MILLISECONDS = 500


def _measure(engine: sa.Engine, *, event_type: str) -> dict[str, float | int | str]:
    benchmark_path = REPOSITORY_ROOT / "scripts" / "benchmark_assignment_change_journal.py"
    specification = spec_from_file_location("assignment_change_journal_benchmark", benchmark_path)
    assert specification is not None
    assert specification.loader is not None
    module = module_from_spec(specification)
    specification.loader.exec_module(module)
    return module.measure(engine, event_type=event_type)


@pytest.mark.db
@pytest.mark.parametrize(
    "event_type",
    [
        "ASSIGNMENT_SCOPE_AMENDED",
        "ASSIGNMENT_SUSPENDED",
        "ASSIGNMENT_REACTIVATED",
        "ASSIGNMENT_ENDED",
    ],
)
def test_assignment_change_journal_performance_budget(
    event_type: str,
    database_engine: sa.Engine,
) -> None:
    """Exercise real PostgreSQL inserts and indexed recent reads over 1,000 rows."""

    result = _measure(database_engine, event_type=event_type)
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))

    assert result["event_type"] == event_type
    assert result["event_count"] == 1_000
    assert result["recent_read_rows"] == 100
    assert result["insert_elapsed_ms"] < MAX_INSERT_MILLISECONDS
    assert result["recent_read_elapsed_ms"] < MAX_RECENT_READ_MILLISECONDS
