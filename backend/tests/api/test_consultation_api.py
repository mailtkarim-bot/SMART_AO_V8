from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from app.bootstrap.application import AppRuntime, create_app
from app.platform.events.dispatcher import CommandContext
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

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
def session_factory(database_engine: sa.Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=database_engine, expire_on_commit=False)


def _insert_tenant(engine: sa.Engine) -> str:
    tenant_id = str(uuid4())
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO tenants (id, slug, lifecycle) VALUES (:id, :slug, 'ACTIVE')"
            ),
            {"id": tenant_id, "slug": f"tenant-{tenant_id}"},
        )
    return tenant_id


def _context(tenant_id: str) -> CommandContext:
    return CommandContext(
        tenant_id=tenant_id,
        actor_id=str(uuid4()),
        actor_kind="PATRON",
        received_at=datetime(2026, 8, 13, 10, 1, tzinfo=UTC),
    )


def _client(
    *,
    session_factory: sessionmaker[Session],
    context: CommandContext,
) -> TestClient:
    runtime = AppRuntime.create(session_factory=session_factory)
    return TestClient(create_app(runtime=runtime, command_context_resolver=lambda: context))


def _payload() -> dict[str, str]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "consultation_id": str(uuid4()),
        "buyer_legal_name": "Ville de test",
        "buyer_normalized_id": "VILLE-TEST",
        "external_reference": "AO-2026-001",
        "object_label": "Réhabilitation école",
        "location_label": "Lille",
        "source_channel": "MANUAL_UPLOAD",
        "source_reference": "Import pilote",
        "source_received_at": "2026-08-13T10:00:00Z",
    }


@pytest.mark.api
@pytest.mark.db
def test_create_consultation_returns_success_and_ryow_projection(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _insert_tenant(database_engine)
    payload = _payload()
    client = _client(session_factory=session_factory, context=_context(tenant_id))

    created = client.post("/api/v1/consultations", json=payload)
    read = client.get(f"/api/v1/consultations/{payload['consultation_id']}")

    assert created.status_code == 201
    assert created.json()["status"] == "SUCCEEDED"
    assert created.json()["result_code"] == "CONSULTATION_CREATED"
    assert created.json()["replayed"] is False
    assert created.json()["projection"]["status"] == "CURRENT"
    assert read.status_code == 200
    assert read.json() == {
        "id": payload["consultation_id"],
        "buyer_legal_name": "Ville de test",
        "external_reference": "AO-2026-001",
        "object_label": "Réhabilitation école",
        "location_label": "Lille",
        "lifecycle": "OPEN",
        "freshness": "UNKNOWN",
        "aggregate_revision": 0,
        "lots": [],
        "tranches": [],
        "projection_status": "CURRENT",
    }


@pytest.mark.api
@pytest.mark.db
def test_create_consultation_replay_returns_saved_success(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _insert_tenant(database_engine)
    payload = _payload()
    client = _client(session_factory=session_factory, context=_context(tenant_id))

    first = client.post("/api/v1/consultations", json=payload)
    replay = client.post("/api/v1/consultations", json=payload)

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["event_ids"] == first.json()["event_ids"]


@pytest.mark.api
@pytest.mark.db
def test_consultation_read_is_neutral_for_another_tenant(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    owner_tenant_id = _insert_tenant(database_engine)
    other_tenant_id = _insert_tenant(database_engine)
    payload = _payload()
    owner_client = _client(session_factory=session_factory, context=_context(owner_tenant_id))
    other_client = _client(session_factory=session_factory, context=_context(other_tenant_id))

    assert owner_client.post("/api/v1/consultations", json=payload).status_code == 201
    response = other_client.get(f"/api/v1/consultations/{payload['consultation_id']}")

    assert response.status_code == 404
    assert response.json()["detail"] == "NOT_FOUND_OR_FORBIDDEN"
