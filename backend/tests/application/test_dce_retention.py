from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from app.modules.dce.application.handlers import ExpireDceStagedObjectHandler
from app.modules.dce.infrastructure.models.consultation import ConsultationRecord
from app.modules.dce.infrastructure.models.dce_staging import DceStagedObjectRecord
from app.modules.dce.infrastructure.quarantine import LocalQuarantineStorageAdapter
from app.platform.events.dispatcher import CommandDispatcher
from app.platform.persistence.models import (
    DomainEventRecord,
    OutboxMessageRecord,
    TenantRecord,
)
from app.workers.dce_retention import RETENTION_TOPIC, DceRetentionWorker
from sqlalchemy.orm import Session, sessionmaker

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPOSITORY_ROOT / "backend" / "alembic.ini"
DATABASE_URL = os.getenv(
    "SMART_AO_TEST_DATABASE_URL",
    "postgresql+psycopg://smart_ao:smart_ao@127.0.0.1:5432/smart_ao",
)
NOW = datetime(2026, 8, 13, 17, 0, tzinfo=UTC)


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


@pytest.fixture(autouse=True)
def isolate_dce_retention_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


async def _stream(content: bytes) -> AsyncIterable[bytes]:
    yield content


def _seed_staged_object(
    session_factory: sessionmaker[Session],
    *,
    state: str,
    expired: bool,
) -> tuple[UUID, UUID, UUID, str]:
    tenant_id, consultation_id, storage_object_id = uuid4(), uuid4(), uuid4()
    storage_key = f"dce-staging/{tenant_id}/{storage_object_id}"
    with session_factory.begin() as session:
        session.add(
            TenantRecord(
                id=tenant_id,
                slug=f"tenant-{tenant_id.hex[:12]}",
                lifecycle="ACTIVE",
            )
        )
        session.flush()
        session.add(
            ConsultationRecord(
                id=consultation_id,
                tenant_id=tenant_id,
                aggregate_revision=4,
                functional_identity_hash="a" * 64,
                buyer_legal_name="Ville de test",
                buyer_normalized_id="VILLE-TEST",
                external_reference="AO-2026-RETENTION",
                object_label="Réhabilitation école",
                location_label="Lille",
                source_channel="MANUAL_UPLOAD",
                source_reference="Fixture retention",
                source_received_at=NOW,
                lifecycle="OPEN",
                freshness="CURRENT",
                metadata_history_json=[],
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
        clean_metadata = state == "CLEAN"
        session.add(
            DceStagedObjectRecord(
                id=storage_object_id,
                tenant_id=tenant_id,
                consultation_id=consultation_id,
                storage_key=storage_key,
                original_filename="Reglement-consultation.pdf",
                expected_byte_size=8,
                actual_byte_size=8 if clean_metadata else None,
                sha256="a" * 64 if clean_metadata else None,
                media_type="application/pdf" if clean_metadata else None,
                source_channel="MANUAL_UPLOAD",
                state=state,
                scan_verdict="CLEAN" if clean_metadata else None,
                scanner_name="test-clamd" if clean_metadata else None,
                scanner_signature_version="test-signatures" if clean_metadata else None,
                scanned_at=NOW if clean_metadata else None,
                rejection_code="SCAN_ERROR" if state == "REJECTED" else None,
                expires_at=NOW - timedelta(minutes=1) if expired else NOW + timedelta(days=1),
                consumed_by_dce_version_id=None,
                consumed_at=None,
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
    return tenant_id, consultation_id, storage_object_id, storage_key


def _seed_retention_outbox(
    session_factory: sessionmaker[Session],
    *,
    tenant_id: UUID,
    storage_object_id: UUID,
) -> UUID:
    event_id, message_id = uuid4(), uuid4()
    payload = {
        "event_id": str(event_id),
        "event_type": "DCE_STAGING_EXPIRED",
        "aggregate_type": "DCE_STAGED_OBJECT",
        "aggregate_id": str(storage_object_id),
        "aggregate_revision": 0,
        "data": {
            "storage_object_id": str(storage_object_id),
            "tenant_id": str(tenant_id),
        },
    }
    with session_factory.begin() as session:
        session.add(
            DomainEventRecord(
                id=event_id,
                tenant_id=tenant_id,
                aggregate_type="DCE_STAGED_OBJECT",
                aggregate_id=storage_object_id,
                aggregate_revision=0,
                event_type="DCE_STAGING_EXPIRED",
                payload_version=1,
                payload_json=payload,
                actor_id=None,
                command_id=None,
                correlation_id=None,
                causation_id=None,
            )
        )
        session.add(
            OutboxMessageRecord(
                id=message_id,
                tenant_id=tenant_id,
                event_id=event_id,
                topic=RETENTION_TOPIC,
                payload_version=1,
                payload_json=payload,
                status="PENDING",
                attempt_count=0,
                next_attempt_at=None,
                published_at=None,
                dedupe_key=f"{RETENTION_TOPIC}:{event_id}",
            )
        )
    return message_id


def _worker(
    *,
    session_factory: sessionmaker[Session],
    storage,
) -> DceRetentionWorker:
    return DceRetentionWorker(
        session_factory=session_factory,
        dispatcher=CommandDispatcher(
            session_factory=session_factory,
            handlers={"ExpireDceStagedObject": ExpireDceStagedObjectHandler()},
        ),
        storage=storage,
    )


def _write_private_file(storage: LocalQuarantineStorageAdapter, *, storage_key: str) -> None:
    asyncio.run(
        storage.write(
            storage_key=storage_key,
            stream=_stream(b"orphaned"),
            max_bytes=2_000_000_000,
        )
    )


@pytest.mark.db
@pytest.mark.integration
def test_retention_deletes_rejected_file_publishes_outbox_and_is_idempotent(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    tenant_id, _, storage_object_id, storage_key = _seed_staged_object(
        session_factory,
        state="REJECTED",
        expired=False,
    )
    message_id = _seed_retention_outbox(
        session_factory,
        tenant_id=tenant_id,
        storage_object_id=storage_object_id,
    )
    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    _write_private_file(storage, storage_key=storage_key)
    worker = _worker(session_factory=session_factory, storage=storage)

    first = asyncio.run(worker.run_once(now=NOW))
    second = asyncio.run(worker.run_once(now=NOW))

    assert first.published == 1
    assert second.published == 0
    assert not (tmp_path / storage_key).exists()
    with session_factory() as session:
        message = session.get(OutboxMessageRecord, message_id)
        staged_object = session.get(DceStagedObjectRecord, storage_object_id)
    assert message is not None
    assert message.status == "PUBLISHED"
    assert staged_object is not None
    assert staged_object.state == "REJECTED"


@pytest.mark.db
@pytest.mark.integration
def test_retention_treats_missing_terminal_file_as_idempotent_success(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    tenant_id, _, storage_object_id, _ = _seed_staged_object(
        session_factory,
        state="EXPIRED",
        expired=True,
    )
    message_id = _seed_retention_outbox(
        session_factory,
        tenant_id=tenant_id,
        storage_object_id=storage_object_id,
    )

    result = asyncio.run(
        _worker(
            session_factory=session_factory,
            storage=LocalQuarantineStorageAdapter(root=tmp_path),
        ).run_once(now=NOW)
    )

    assert result.published == 1
    with session_factory() as session:
        message = session.get(OutboxMessageRecord, message_id)
    assert message is not None
    assert message.status == "PUBLISHED"


@pytest.mark.db
@pytest.mark.integration
def test_retention_never_deletes_clean_file_even_for_retention_message(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    tenant_id, _, storage_object_id, storage_key = _seed_staged_object(
        session_factory,
        state="CLEAN",
        expired=False,
    )
    _seed_retention_outbox(
        session_factory,
        tenant_id=tenant_id,
        storage_object_id=storage_object_id,
    )
    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    _write_private_file(storage, storage_key=storage_key)

    worker = _worker(session_factory=session_factory, storage=storage)
    result = asyncio.run(worker.run_once(now=NOW))

    assert result.skipped == 1
    assert (tmp_path / storage_key).read_bytes() == b"orphaned"


@pytest.mark.db
@pytest.mark.integration
def test_retention_retries_private_delete_failure_with_bounded_backoff(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    class FailingStorage(LocalQuarantineStorageAdapter):
        async def delete(self, *, storage_key: str) -> None:
            raise OSError("storage unavailable")

    tenant_id, _, storage_object_id, _ = _seed_staged_object(
        session_factory,
        state="REJECTED",
        expired=False,
    )
    message_id = _seed_retention_outbox(
        session_factory,
        tenant_id=tenant_id,
        storage_object_id=storage_object_id,
    )

    result = asyncio.run(
        _worker(
            session_factory=session_factory,
            storage=FailingStorage(root=tmp_path),
        ).run_once(now=NOW)
    )

    assert result.retried == 1
    with session_factory() as session:
        message = session.get(OutboxMessageRecord, message_id)
    assert message is not None
    assert message.status == "RETRY"
    assert message.attempt_count == 1
    assert message.last_error_code == "PRIVATE_DELETE_FAILED"
    assert message.next_attempt_at == NOW + timedelta(seconds=30)


@pytest.mark.db
@pytest.mark.integration
def test_retention_expires_uploading_orphan_then_deletes_its_private_file(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    _, _, storage_object_id, storage_key = _seed_staged_object(
        session_factory,
        state="UPLOADING",
        expired=True,
    )
    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    _write_private_file(storage, storage_key=storage_key)

    worker = _worker(session_factory=session_factory, storage=storage)
    result = asyncio.run(worker.run_once(now=NOW))

    assert result.expired == 1
    assert result.published == 1
    assert not (tmp_path / storage_key).exists()
    with session_factory() as session:
        staged_object = session.get(DceStagedObjectRecord, storage_object_id)
        outbox = list(session.scalars(sa.select(OutboxMessageRecord)))
    assert staged_object is not None
    assert staged_object.state == "EXPIRED"
    assert [message.status for message in outbox] == ["PUBLISHED"]
