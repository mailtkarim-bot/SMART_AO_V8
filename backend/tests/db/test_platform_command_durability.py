from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import IntegrityError

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPOSITORY_ROOT / "backend" / "alembic.ini"
DATABASE_URL = os.getenv(
    "SMART_AO_TEST_DATABASE_URL",
    "postgresql+psycopg://smart_ao:smart_ao@127.0.0.1:5432/smart_ao",
)


@pytest.fixture(scope="module")
def database_engine() -> sa.Engine:
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
def connection(database_engine: sa.Engine):
    with database_engine.begin() as transaction:
        yield transaction


def _insert_tenant(connection: sa.Connection, *, slug: str | None = None) -> str:
    tenant_id = str(uuid4())
    tenant_slug = slug or f"tenant-{tenant_id}"
    connection.execute(
        sa.text(
            """
            INSERT INTO tenants (id, slug, lifecycle)
            VALUES (:id, :slug, 'ACTIVE')
            """
        ),
        {"id": tenant_id, "slug": tenant_slug},
    )
    return tenant_id


@pytest.mark.db
def test_initial_migration_creates_platform_durability_tables(database_engine: sa.Engine) -> None:
    inspector = sa.inspect(database_engine)

    assert {
        "tenants",
        "command_receipts",
        "domain_events",
        "outbox_messages",
        "process_inbox",
    }.issubset(set(inspector.get_table_names()))


@pytest.mark.db
def test_tenant_slug_is_unique(connection: sa.Connection) -> None:
    _insert_tenant(connection, slug="one-company")

    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            sa.text(
                """
                INSERT INTO tenants (id, slug, lifecycle)
                VALUES (:id, 'one-company', 'ACTIVE')
                """
            ),
            {"id": str(uuid4())},
        )


@pytest.mark.db
def test_receipt_unique_key_blocks_duplicate_intention_for_same_actor(
    connection: sa.Connection,
) -> None:
    tenant_id = _insert_tenant(connection)
    actor_id = str(uuid4())
    idempotency_key = str(uuid4())
    receipt_parameters = {
        "id": str(uuid4()),
        "tenant_id": tenant_id,
        "actor_id": actor_id,
        "command_id": str(uuid4()),
        "command_type": "CreateCase",
        "idempotency_key": idempotency_key,
        "request_hash": "a" * 64,
    }
    insert_statement = sa.text(
        """
        INSERT INTO command_receipts (
            id, tenant_id, actor_id, command_id, command_type,
            idempotency_key, request_hash, status
        ) VALUES (
            :id, :tenant_id, :actor_id, :command_id, :command_type,
            :idempotency_key, :request_hash, 'PROCESSING'
        )
        """
    )
    connection.execute(insert_statement, receipt_parameters)

    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            insert_statement,
            {
                **receipt_parameters,
                "id": str(uuid4()),
                "command_id": str(uuid4()),
            },
        )


@pytest.mark.db
def test_same_idempotency_key_for_another_actor_is_allowed(connection: sa.Connection) -> None:
    tenant_id = _insert_tenant(connection)
    shared_key = str(uuid4())
    insert_statement = sa.text(
        """
        INSERT INTO command_receipts (
            id, tenant_id, actor_id, command_id, command_type,
            idempotency_key, request_hash, status
        ) VALUES (
            :id, :tenant_id, :actor_id, :command_id, 'CreateCase',
            :idempotency_key, :request_hash, 'PROCESSING'
        )
        """
    )

    for actor_id in (str(uuid4()), str(uuid4())):
        connection.execute(
            insert_statement,
            {
                "id": str(uuid4()),
                "tenant_id": tenant_id,
                "actor_id": actor_id,
                "command_id": str(uuid4()),
                "idempotency_key": shared_key,
                "request_hash": "b" * 64,
            },
        )

    count = connection.scalar(
        sa.text("SELECT count(*) FROM command_receipts WHERE tenant_id = :tenant_id"),
        {"tenant_id": tenant_id},
    )
    assert count == 2


@pytest.mark.db
def test_outbox_requires_an_existing_event_of_the_same_tenant(connection: sa.Connection) -> None:
    tenant_id = _insert_tenant(connection)

    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            sa.text(
                """
                INSERT INTO outbox_messages (
                    id, tenant_id, event_id, topic, payload_version,
                    payload_json, status, dedupe_key
                ) VALUES (
                    :id, :tenant_id, :event_id, 'case.created.v1', 1,
                    CAST('{}' AS jsonb), 'PENDING', :dedupe_key
                )
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": tenant_id,
                "event_id": str(uuid4()),
                "dedupe_key": "event:missing:case.created.v1",
            },
        )


@pytest.mark.db
def test_event_and_outbox_are_rolled_back_together_when_transaction_fails(
    database_engine: sa.Engine,
) -> None:
    tenant_id = str(uuid4())
    event_id = str(uuid4())
    aggregate_id = str(uuid4())

    with pytest.raises(RuntimeError), database_engine.begin() as transaction:
        transaction.execute(
            sa.text(
                """
                    INSERT INTO tenants (id, slug, lifecycle)
                    VALUES (:id, 'rollback-company', 'ACTIVE')
                    """
            ),
            {"id": tenant_id},
        )
        transaction.execute(
            sa.text(
                """
                    INSERT INTO domain_events (
                        id, tenant_id, aggregate_type, aggregate_id,
                        aggregate_revision, event_type, payload_version, payload_json
                    ) VALUES (
                        :id, :tenant_id, 'Case', :aggregate_id,
                        0, 'CaseCreated', 1, CAST('{}' AS jsonb)
                    )
                    """
            ),
            {
                "id": event_id,
                "tenant_id": tenant_id,
                "aggregate_id": aggregate_id,
            },
        )
        transaction.execute(
            sa.text(
                """
                    INSERT INTO outbox_messages (
                        id, tenant_id, event_id, topic, payload_version,
                        payload_json, status, dedupe_key
                    ) VALUES (
                        :id, :tenant_id, :event_id, 'case.created.v1', 1,
                        CAST('{}' AS jsonb), 'PENDING', :dedupe_key
                    )
                    """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": tenant_id,
                "event_id": event_id,
                "dedupe_key": f"{event_id}:case.created.v1",
            },
        )
        raise RuntimeError("simulate failure before commit")

    with database_engine.connect() as connection:
        assert connection.scalar(
            sa.text("SELECT count(*) FROM tenants WHERE id = :tenant_id"),
            {"tenant_id": tenant_id},
        ) == 0
        assert connection.scalar(
            sa.text("SELECT count(*) FROM domain_events WHERE id = :event_id"),
            {"event_id": event_id},
        ) == 0
        assert connection.scalar(
            sa.text("SELECT count(*) FROM outbox_messages WHERE event_id = :event_id"),
            {"event_id": event_id},
        ) == 0
