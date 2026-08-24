from __future__ import annotations

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session, sessionmaker

from tests.support.database import ALEMBIC_INI, DATABASE_URL


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Classify all tests whose fixture closure requires the real PostgreSQL service."""
    db_fixtures = {"database_engine", "session_factory"}
    for item in items:
        if db_fixtures.intersection(item.fixturenames):
            item.add_marker(pytest.mark.db)


@pytest.fixture(scope="module")
def database_engine() -> sa.Engine:
    """Create one isolated Alembic schema per test module."""
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    command.upgrade(config, "head")
    engine = sa.create_engine(DATABASE_URL)
    try:
        yield engine
    finally:
        engine.dispose()
        command.downgrade(config, "base")


@pytest.fixture
def session_factory(database_engine: sa.Engine) -> sessionmaker[Session]:
    """Provide the same non-expiring session factory to every DB test."""
    return sessionmaker(bind=database_engine, expire_on_commit=False)
