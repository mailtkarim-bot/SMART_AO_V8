import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPOSITORY_ROOT / "backend" / "alembic.ini"
DATABASE_URL = os.getenv("SMART_AO_TEST_DATABASE_URL") or (
    "postgresql+psycopg://"
    + "smart_ao"
    + ":"
    + "smart_ao"
    + "@127.0.0.1:5432/smart_ao"
)

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
def test_assignment_change_journal_performance_budget(event_type: str) -> None:
    """Exercise real PostgreSQL inserts and indexed recent reads over 1,000 rows."""

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    command.upgrade(config, "head")
    engine = sa.create_engine(DATABASE_URL)
    try:
        result = _measure(engine, event_type=event_type)
    finally:
        with engine.begin() as connection:
            connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))
        engine.dispose()
        command.downgrade(config, "base")

    assert result["event_type"] == event_type
    assert result["event_count"] == 1_000
    assert result["recent_read_rows"] == 100
    assert result["insert_elapsed_ms"] < MAX_INSERT_MILLISECONDS
    assert result["recent_read_elapsed_ms"] < MAX_RECENT_READ_MILLISECONDS
