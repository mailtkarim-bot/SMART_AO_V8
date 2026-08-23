"""Publish BOAMP qualification notifications from the transactional outbox."""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.platform.events.external_bus import (
    ExternalEventBusDeliveryError,
    ExternalEventBusPort,
    HttpExternalEventBus,
)
from app.platform.persistence.models import OutboxMessageRecord

BOAMP_INGESTION_TOPIC = "opportunity.boamp.ingestion.recorded"
BOAMP_QUALIFICATION_TOPIC = "opportunity.boamp.qualification.recorded"
BOAMP_TOPICS = frozenset({BOAMP_INGESTION_TOPIC, BOAMP_QUALIFICATION_TOPIC})
PROCESS_NAME = "opportunity-event-bus"


@dataclass(frozen=True, slots=True)
class EventBusRunResult:
    delivered: int = 0
    skipped: int = 0
    retried: int = 0


class OpportunityEventBusWorker:
    """Lease and publish one outbox topic without exposing rich opportunity data."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        bus: ExternalEventBusPort | None,
        batch_size: int = 50,
        lease_seconds: int = 120,
    ) -> None:
        if not 1 <= batch_size <= 200:
            raise ValueError("batch_size must be between 1 and 200")
        if not 1 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 1 and 3600")
        self._session_factory = session_factory
        self._bus = bus
        self._batch_size = batch_size
        self._lease_seconds = lease_seconds

    def run_once(self, *, now: datetime | None = None) -> EventBusRunResult:
        effective_now = now or datetime.now(tz=UTC)
        message_ids = self._claim_due_messages(now=effective_now)
        result = EventBusRunResult()
        for message_id in message_ids:
            result = _merge(result, self._process_message(message_id, effective_now))
        return result

    def _claim_due_messages(self, *, now: datetime) -> list[UUID]:
        lease_until = now + timedelta(seconds=self._lease_seconds)
        with self._session_factory.begin() as session:
            messages = list(
                session.scalars(
                    sa.select(OutboxMessageRecord)
                    .where(
                        OutboxMessageRecord.topic.in_(BOAMP_TOPICS),
                        OutboxMessageRecord.status.in_(("PENDING", "RETRY")),
                        sa.or_(
                            OutboxMessageRecord.next_attempt_at.is_(None),
                            OutboxMessageRecord.next_attempt_at <= now,
                        ),
                    )
                    .order_by(OutboxMessageRecord.created_at, OutboxMessageRecord.id)
                    .limit(self._batch_size)
                    .with_for_update(skip_locked=True)
                )
            )
            for message in messages:
                message.status = "RETRY"
                message.next_attempt_at = lease_until
            return [message.id for message in messages]

    def _process_message(self, message_id: UUID, now: datetime) -> EventBusRunResult:
        with self._session_factory() as session:
            message = session.get(OutboxMessageRecord, message_id)
            if message is None or message.topic not in BOAMP_TOPICS:
                return EventBusRunResult(skipped=1)
            payload = _safe_payload(message.topic, message.payload_json)
            if payload is None:
                return self._retry(message_id, now, "INVALID_BOAMP_EVENT_PAYLOAD")
            if self._bus is None:
                return EventBusRunResult(skipped=1)
            event_id = message.event_id
            tenant_id = message.tenant_id
        try:
            self._bus.publish(
                event_id=event_id,
                tenant_id=tenant_id,
                topic=message.topic,
                payload=payload,
            )
        except (ExternalEventBusDeliveryError, OSError, ValueError):
            return self._retry(message_id, now, "EXTERNAL_EVENT_BUS_DELIVERY_FAILED")
        return self._publish(message_id, now)

    def _publish(
        self, message_id: UUID, now: datetime, *, skipped: bool = False
    ) -> EventBusRunResult:
        with self._session_factory.begin() as session:
            message = session.get(OutboxMessageRecord, message_id, with_for_update=True)
            if message is None or message.status == "PUBLISHED":
                return EventBusRunResult(skipped=1)
            message.status = "PUBLISHED"
            message.published_at = now
            message.next_attempt_at = None
            message.last_error_code = None
        return EventBusRunResult(skipped=1) if skipped else EventBusRunResult(delivered=1)

    def _retry(self, message_id: UUID, now: datetime, error_code: str) -> EventBusRunResult:
        with self._session_factory.begin() as session:
            message = session.get(OutboxMessageRecord, message_id, with_for_update=True)
            if message is None or message.status == "PUBLISHED":
                return EventBusRunResult(skipped=1)
            message.status = "RETRY"
            message.attempt_count += 1
            message.next_attempt_at = now + _retry_delay(message.attempt_count)
            message.last_error_code = error_code
        return EventBusRunResult(retried=1)


def _safe_payload(topic: str, payload_json: object) -> dict[str, object] | None:
    if not isinstance(payload_json, dict):
        return None
    if topic == BOAMP_INGESTION_TOPIC:
        allowed = {"ingestion_run_id", "observation_count", "request_hash"}
        if set(payload_json) != allowed:
            return None
        if not isinstance(payload_json["ingestion_run_id"], str):
            return None
        if not isinstance(payload_json["observation_count"], int):
            return None
        request_hash = payload_json["request_hash"]
        if not isinstance(request_hash, str) or len(request_hash) != 64:
            return None
        return dict(payload_json)
    if topic == BOAMP_QUALIFICATION_TOPIC:
        allowed = {"qualification_id", "observation_id", "decision", "reason_code"}
        if set(payload_json) != allowed:
            return None
        if not all(isinstance(payload_json[key], str) for key in allowed):
            return None
        if payload_json["decision"] not in {"QUALIFIED", "REJECTED", "SNOOZED"}:
            return None
        return dict(payload_json)
    return None


def _merge(first: EventBusRunResult, second: EventBusRunResult) -> EventBusRunResult:
    return EventBusRunResult(
        delivered=first.delivered + second.delivered,
        skipped=first.skipped + second.skipped,
        retried=first.retried + second.retried,
    )


def _retry_delay(attempt_count: int) -> timedelta:
    return timedelta(seconds=min(30 * (2 ** max(attempt_count - 1, 0)), 3600))


def external_event_bus_enabled(environ: Mapping[str, str] | None = None) -> bool:
    values = environ if environ is not None else os.environ
    return values.get("SMART_AO_EXTERNAL_EVENT_BUS_ENABLED", "0") == "1"


def build_default_worker() -> OpportunityEventBusWorker:
    if not external_event_bus_enabled():
        raise RuntimeError("external event bus worker is disabled")
    database_url = os.environ["SMART_AO_DATABASE_URL"]
    bus_url = os.getenv("SMART_AO_EXTERNAL_EVENT_BUS_URL") or None
    bus_token = os.getenv("SMART_AO_EXTERNAL_EVENT_BUS_TOKEN") or None
    if not bus_url or not bus_token:
        raise RuntimeError(
            "external event bus requires SMART_AO_EXTERNAL_EVENT_BUS_URL and "
            "SMART_AO_EXTERNAL_EVENT_BUS_TOKEN"
        )
    engine = sa.create_engine(database_url)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    bus = HttpExternalEventBus(url=bus_url, token=bus_token)
    return OpportunityEventBusWorker(
        session_factory=sessions,
        bus=bus,
        batch_size=int(os.getenv("SMART_AO_EXTERNAL_EVENT_BUS_BATCH_SIZE", "50")),
        lease_seconds=int(os.getenv("SMART_AO_EXTERNAL_EVENT_BUS_LEASE_SECONDS", "120")),
    )


def main() -> None:
    if not external_event_bus_enabled():
        print("external event bus worker disabled")
        return
    worker = build_default_worker()
    poll_seconds = float(os.getenv("SMART_AO_EXTERNAL_EVENT_BUS_POLL_SECONDS", "30"))
    while True:
        worker.run_once()
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
