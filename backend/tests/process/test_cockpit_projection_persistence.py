from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord, TenantRecord
from app.workers.cockpit_projection import (
    COCKPIT_PROJECTION_TOPIC,
    CockpitProjectionDeliveryError,
    CockpitProjectionWorker,
)
from sqlalchemy.orm import Session, sessionmaker

pytestmark = [pytest.mark.db, pytest.mark.process]
NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


def _valid_payload(tenant_id: UUID) -> dict[str, object]:
    return {
        "event_id": str(uuid4()),
        "event_type": "DCE_STAGING_SCAN_RECORDED",
        "aggregate_type": "DCE_STAGED_OBJECT",
        "aggregate_id": str(uuid4()),
        "aggregate_revision": 0,
        "data": {
            "storage_object_id": str(uuid4()),
            "tenant_id": str(tenant_id),
            "consultation_id": str(uuid4()),
            "state": "SCANNED",
        },
    }


def _seed_message(
    session_factory: sessionmaker[Session],
    *,
    payload: dict[str, object] | None = None,
) -> tuple[UUID, UUID]:
    tenant_id = uuid4()
    event_id = uuid4()
    message_id = uuid4()
    with session_factory.begin() as session:
        session.add(
            TenantRecord(
                id=tenant_id,
                slug=f"cockpit-{tenant_id.hex[:12]}",
                lifecycle="ACTIVE",
            )
        )
        session.flush()
        session.add(
            DomainEventRecord(
                id=event_id,
                tenant_id=tenant_id,
                aggregate_type="DCE_STAGED_OBJECT",
                aggregate_id=uuid4(),
                aggregate_revision=0,
                event_type="DCE_STAGING_SCAN_RECORDED",
                payload_version=1,
                payload_json=payload or _valid_payload(tenant_id),
                actor_id=None,
                command_id=uuid4(),
                correlation_id=None,
                occurred_at=NOW,
            )
        )
        session.add(
            OutboxMessageRecord(
                id=message_id,
                tenant_id=tenant_id,
                event_id=event_id,
                topic=COCKPIT_PROJECTION_TOPIC,
                payload_version=1,
                payload_json=payload or _valid_payload(tenant_id),
                status="PENDING",
                attempt_count=0,
                next_attempt_at=None,
                published_at=None,
                last_error_code=None,
                dedupe_key=f"cockpit:{event_id}",
            )
        )
    return tenant_id, message_id


def _read_message(
    session_factory: sessionmaker[Session], message_id: UUID
) -> OutboxMessageRecord:
    with session_factory() as session:
        message = session.get(OutboxMessageRecord, message_id)
        assert message is not None
        return message


class RecordingProjection:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def apply(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


class FailingProjection:
    def apply(self, **_kwargs: object) -> None:
        raise CockpitProjectionDeliveryError("projection unavailable")


def test_worker_publishes_valid_postgres_outbox_after_projection_ack(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, message_id = _seed_message(session_factory)
    projection = RecordingProjection()
    worker = CockpitProjectionWorker(
        session_factory=session_factory,
        projection=projection,
        batch_size=10,
        lease_seconds=60,
    )

    result = worker.run_once(now=NOW)

    assert result.delivered == 1
    assert len(projection.calls) == 1
    assert projection.calls[0]["tenant_id"] == tenant_id
    message = _read_message(session_factory, message_id)
    assert message.status == "PUBLISHED"
    assert message.published_at == NOW
    assert message.attempt_count == 0
    assert message.next_attempt_at is None


def test_worker_marks_projection_not_configured_as_terminal(
    session_factory: sessionmaker[Session],
) -> None:
    _tenant_id, message_id = _seed_message(session_factory)
    worker = CockpitProjectionWorker(session_factory=session_factory, projection=None)

    result = worker.run_once(now=NOW)

    assert result.not_configured == 1
    message = _read_message(session_factory, message_id)
    assert message.status == "NOT_CONFIGURED"
    assert message.last_error_code == "COCKPIT_PROJECTION_NOT_CONFIGURED"
    assert message.next_attempt_at is None


def test_worker_rejects_invalid_payload_as_terminal_failure(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = uuid4()
    invalid_payload = _valid_payload(tenant_id)
    del invalid_payload["data"]
    _tenant_id, message_id = _seed_message(session_factory, payload=invalid_payload)
    worker = CockpitProjectionWorker(
        session_factory=session_factory,
        projection=RecordingProjection(),
    )

    result = worker.run_once(now=NOW)

    assert result.failed == 1
    message = _read_message(session_factory, message_id)
    assert message.status == "FAILED"
    assert message.attempt_count == 1
    assert message.last_error_code == "INVALID_COCKPIT_EVENT_PAYLOAD"
    assert message.next_attempt_at is None


def test_worker_retries_then_fails_after_max_attempts(
    session_factory: sessionmaker[Session],
) -> None:
    _tenant_id, message_id = _seed_message(session_factory)
    worker = CockpitProjectionWorker(
        session_factory=session_factory,
        projection=FailingProjection(),
        max_attempts=2,
    )

    first = worker.run_once(now=NOW)
    second = worker.run_once(now=NOW + timedelta(seconds=30))

    assert first.retried == 1
    assert first.failed == 0
    assert second.retried == 0
    assert second.failed == 1
    message = _read_message(session_factory, message_id)
    assert message.status == "FAILED"
    assert message.attempt_count == 2
    assert message.last_error_code == "COCKPIT_PROJECTION_DELIVERY_FAILED"
    assert message.next_attempt_at is None


def test_worker_lease_prevents_a_second_claim_before_expiry(
    session_factory: sessionmaker[Session],
) -> None:
    _tenant_id, message_id = _seed_message(session_factory)
    worker = CockpitProjectionWorker(
        session_factory=session_factory,
        projection=RecordingProjection(),
        lease_seconds=120,
    )

    first_claim = worker._claim_due_messages(now=NOW)
    second_claim = worker._claim_due_messages(now=NOW)

    assert first_claim == [message_id]
    assert second_claim == []
    message = _read_message(session_factory, message_id)
    assert message.status == "RETRY"
    assert message.next_attempt_at == NOW + timedelta(seconds=120)
