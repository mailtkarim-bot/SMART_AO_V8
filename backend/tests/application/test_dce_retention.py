from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import app.workers.dce_retention as retention_module
import pytest
import sqlalchemy as sa
from app.modules.dce.application.handlers import ExpireDceStagedObjectHandler
from app.modules.dce.infrastructure.models.consultation import ConsultationRecord
from app.modules.dce.infrastructure.models.dce_staging import DceStagedObjectRecord
from app.modules.dce.infrastructure.quarantine import LocalQuarantineStorageAdapter
from app.platform.events.dispatcher import CommandDispatcher, CommandExecutionError
from app.platform.persistence.models import (
    DomainEventRecord,
    OutboxMessageRecord,
    TenantRecord,
)
from app.workers.dce_retention import RETENTION_TOPIC, DceRetentionWorker
from sqlalchemy.orm import Session, sessionmaker

NOW = datetime(2026, 8, 13, 17, 0, tzinfo=UTC)






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


def test_retention_run_result_merges_all_counters() -> None:
    first = retention_module.RetentionRunResult(expired=1, published=2)
    second = retention_module.RetentionRunResult(retried=3, skipped=4)

    assert first.merged(second) == retention_module.RetentionRunResult(
        expired=1, published=2, retried=3, skipped=4
    )


@pytest.mark.parametrize(
    ("payload", "key"),
    [(None, "tenant_id"), ({"tenant_id": "not-a-uuid"}, "tenant_id"), ({}, "missing")],
)
def test_retention_uuid_payload_rejects_invalid_values(payload: object, key: str) -> None:
    assert retention_module._uuid_payload(payload, key) is None  # noqa: SLF001


def test_retention_expiry_continues_after_dispatch_rejection() -> None:
    storage_object_id = uuid4()
    tenant_id = uuid4()
    transaction = MagicMock()
    transaction.scalars.side_effect = [
        [SimpleNamespace(id=storage_object_id)],
        [SimpleNamespace(id=storage_object_id, tenant_id=tenant_id)],
    ]
    factory = MagicMock()
    factory.begin.return_value.__enter__.return_value = transaction
    dispatcher = MagicMock()
    dispatcher.dispatch.side_effect = CommandExecutionError("already-expired")
    worker = DceRetentionWorker(
        session_factory=factory,
        dispatcher=dispatcher,
        storage=MagicMock(),
    )

    assert worker._expire_due_objects(now=NOW) == 0  # noqa: SLF001
    dispatcher.dispatch.assert_called_once()


def _message_factory(message: object) -> MagicMock:
    factory = MagicMock()
    read_session = MagicMock()
    read_session.get.return_value = message
    factory.return_value.__enter__.return_value = read_session
    write_session = MagicMock()
    write_session.get.return_value = message
    factory.begin.return_value.__enter__.return_value = write_session
    return factory


def test_retention_process_skips_missing_and_wrong_topic_messages() -> None:
    worker = DceRetentionWorker(
        session_factory=_message_factory(None),
        dispatcher=MagicMock(),
        storage=MagicMock(),
    )
    assert asyncio.run(worker._process_message(message_id=uuid4(), now=NOW)).skipped == 1  # noqa: SLF001
    wrong = SimpleNamespace(topic="other.topic")
    worker = DceRetentionWorker(
        session_factory=_message_factory(wrong),
        dispatcher=MagicMock(),
        storage=MagicMock(),
    )
    assert asyncio.run(worker._process_message(message_id=uuid4(), now=NOW)).skipped == 1  # noqa: SLF001


def test_retention_process_retries_invalid_payload() -> None:
    message = SimpleNamespace(
        topic=RETENTION_TOPIC,
        payload_json={"data": {}},
        status="RETRY",
        attempt_count=0,
    )
    factory = _message_factory(message)
    worker = DceRetentionWorker(
        session_factory=factory,
        dispatcher=MagicMock(),
        storage=MagicMock(),
    )

    result = asyncio.run(worker._process_message(message_id=uuid4(), now=NOW))  # noqa: SLF001

    assert result.retried == 1
    assert message.last_error_code == "INVALID_RETENTION_PAYLOAD"


def test_retention_publish_and_retry_are_idempotent_for_published_message() -> None:
    message = SimpleNamespace(status="PUBLISHED")
    worker = DceRetentionWorker(
        session_factory=_message_factory(message),
        dispatcher=MagicMock(),
        storage=MagicMock(),
    )

    assert worker._publish_message(message_id=uuid4(), now=NOW).skipped == 1  # noqa: SLF001
    assert worker._retry_message(  # noqa: SLF001
        message_id=uuid4(), now=NOW, error_code="ignored"
    ).skipped == 1


def test_retention_build_default_worker_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = object()
    session_factory = object()
    monkeypatch.setenv("SMART_AO_DATABASE_URL", "postgresql://test")
    monkeypatch.setenv("SMART_AO_DCE_QUARANTINE_ROOT", "/tmp/quarantine")
    monkeypatch.setenv("SMART_AO_RETENTION_BATCH_SIZE", "3")
    monkeypatch.setenv("SMART_AO_RETENTION_LEASE_SECONDS", "7")
    monkeypatch.setattr(retention_module.sa, "create_engine", lambda url: (url, engine))
    monkeypatch.setattr(
        retention_module, "sessionmaker", lambda bind, expire_on_commit: session_factory
    )
    monkeypatch.setattr(retention_module, "CommandDispatcher", lambda **_kwargs: "dispatcher")
    monkeypatch.setattr(
        retention_module,
        "LocalQuarantineStorageAdapter",
        lambda root: ("storage", root),
    )

    worker = retention_module.build_default_worker()

    assert worker._session_factory is session_factory
    assert worker._batch_size == 3
    assert worker._lease_seconds == 7


def test_retention_main_runs_one_poll_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    worker = MagicMock()
    monkeypatch.setattr(retention_module, "build_default_worker", lambda: worker)
    monkeypatch.setattr(asyncio, "run", lambda coroutine: coroutine.close())
    monkeypatch.setenv("SMART_AO_RETENTION_POLL_SECONDS", "0")

    def stop(_seconds: float) -> None:
        raise RuntimeError("stop retention loop")

    monkeypatch.setattr(retention_module.time, "sleep", stop)
    with pytest.raises(RuntimeError, match="stop retention loop"):
        retention_module.main()
