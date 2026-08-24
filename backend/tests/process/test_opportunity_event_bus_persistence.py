from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.platform.events.external_bus import ExternalEventBusDeliveryError, InMemoryExternalEventBus
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord, TenantRecord
from app.workers.opportunity_event_bus import (
    BOAMP_QUALIFICATION_TOPIC,
    OpportunityEventBusWorker,
)
from sqlalchemy.orm import Session, sessionmaker

pytestmark = [pytest.mark.db, pytest.mark.process]
NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)


def _seed_outbox(
    session_factory: sessionmaker[Session], *, status: str = "PENDING"
) -> tuple[UUID, UUID]:
    tenant_id = uuid4()
    event_id = uuid4()
    message_id = uuid4()
    with session_factory.begin() as session:
        session.add(
            TenantRecord(
                id=tenant_id,
                slug=f"worker-{tenant_id.hex[:12]}",
                lifecycle="ACTIVE",
            )
        )
        session.flush()
        session.add(
            DomainEventRecord(
                id=event_id,
                tenant_id=tenant_id,
                aggregate_type="BoampOpportunityQualification",
                aggregate_id=uuid4(),
                aggregate_revision=1,
                event_type="BoampOpportunityQualified",
                payload_version=1,
                payload_json={"qualification_id": str(uuid4())},
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
                topic=BOAMP_QUALIFICATION_TOPIC,
                payload_version=1,
                payload_json={
                    "qualification_id": str(uuid4()),
                    "observation_id": str(uuid4()),
                    "decision": "QUALIFIED",
                    "reason_code": "RELEVANT_PUBLIC_SIGNAL",
                },
                status=status,
                attempt_count=0,
                next_attempt_at=None,
                published_at=None,
                last_error_code=None,
                dedupe_key=f"worker:{event_id}",
            )
        )
    return tenant_id, message_id


def test_worker_publishes_postgres_outbox_only_after_ack(
    session_factory: sessionmaker[Session],
) -> None:
    _tenant_id, message_id = _seed_outbox(session_factory)
    deliveries: list[dict[str, object]] = []
    worker = OpportunityEventBusWorker(
        session_factory=session_factory,
        bus=InMemoryExternalEventBus(deliveries),
        batch_size=10,
        lease_seconds=60,
    )

    result = worker.run_once(now=NOW)

    assert result.delivered == 1
    assert len(deliveries) == 1
    with session_factory() as session:
        message = session.get(OutboxMessageRecord, message_id)
        assert message is not None
        assert message.status == "PUBLISHED"
        assert message.published_at == NOW
        assert message.attempt_count == 0


def test_worker_retries_postgres_outbox_after_external_rejection(
    session_factory: sessionmaker[Session],
) -> None:
    _tenant_id, message_id = _seed_outbox(session_factory)

    class FailingBus:
        def publish(self, **_kwargs: object) -> None:
            raise ExternalEventBusDeliveryError("provider unavailable")

    worker = OpportunityEventBusWorker(
        session_factory=session_factory,
        bus=FailingBus(),
        batch_size=10,
        lease_seconds=60,
    )
    result = worker.run_once(now=NOW)

    assert result.retried == 1
    with session_factory() as session:
        message = session.get(OutboxMessageRecord, message_id)
        assert message is not None
        assert message.status == "RETRY"
        assert message.published_at is None
        assert message.attempt_count == 1
        assert message.last_error_code == "EXTERNAL_EVENT_BUS_DELIVERY_FAILED"
        assert message.next_attempt_at == NOW + timedelta(seconds=30)
        assert session.scalar(
            sa.select(sa.func.count(OutboxMessageRecord.id)).where(
                OutboxMessageRecord.status == "PUBLISHED"
            )
        ) == 0
