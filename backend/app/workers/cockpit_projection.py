from __future__ import annotations

import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, TypedDict
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.platform.events.retry_policy import (
    DEFAULT_MAX_OUTBOX_ATTEMPTS,
    MAX_OUTBOX_ATTEMPTS_LIMIT,
    decide_retry,
)
from app.platform.observability.outbox import (
    COCKPIT_PROJECTION_METRICS,
    CockpitProjectionMetrics,
)
from app.platform.persistence.models import OutboxMessageRecord

COCKPIT_PROJECTION_TOPIC = "cockpit_projection"
PROCESS_NAME = "cockpit-projection"
_ALLOWED_EVENT_TYPES = frozenset(
    {"DCE_STAGING_QUARANTINE_RECORDED", "DCE_STAGING_SCAN_RECORDED"}
)
_ALLOWED_DATA_FIELDS = frozenset({"storage_object_id", "tenant_id", "consultation_id", "state"})
_ALLOWED_STATES = frozenset({"PENDING_SCAN", "SCANNED", "REJECTED"})


class CockpitProjectionDeliveryError(RuntimeError):
    """The configured cockpit projection rejected or could not receive an event."""


class SafeCockpitEvent(TypedDict):
    event_id: UUID
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    aggregate_revision: int
    payload: Mapping[str, object]


class CockpitProjectionPort(Protocol):
    def apply(
        self,
        *,
        event_id: UUID,
        tenant_id: UUID,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID,
        aggregate_revision: int,
        payload: Mapping[str, object],
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class CockpitProjectionRunResult:
    delivered: int = 0
    skipped: int = 0
    retried: int = 0
    failed: int = 0
    not_configured: int = 0


class CockpitProjectionWorker:
    """Delivers the closed internal cockpit event contract exactly once per outbox row."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        projection: CockpitProjectionPort | None,
        metrics: CockpitProjectionMetrics | None = None,
        batch_size: int = 50,
        lease_seconds: int = 120,
        max_attempts: int = DEFAULT_MAX_OUTBOX_ATTEMPTS,
    ) -> None:
        if not 1 <= batch_size <= 200:
            raise ValueError("batch_size must be between 1 and 200")
        if not 1 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 1 and 3600")
        if not 1 <= max_attempts <= MAX_OUTBOX_ATTEMPTS_LIMIT:
            raise ValueError("max_attempts must be between 1 and 100")
        self._session_factory = session_factory
        self._projection = projection
        self._metrics = metrics or COCKPIT_PROJECTION_METRICS
        self._batch_size = batch_size
        self._lease_seconds = lease_seconds
        self._max_attempts = max_attempts

    @property
    def metrics(self) -> CockpitProjectionMetrics:
        return self._metrics

    def run_once(self, *, now: datetime | None = None) -> CockpitProjectionRunResult:
        effective_now = now or datetime.now(tz=UTC)
        message_ids = self._claim_due_messages(now=effective_now)
        result = CockpitProjectionRunResult()
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
                        OutboxMessageRecord.topic == COCKPIT_PROJECTION_TOPIC,
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

    def _process_message(self, message_id: UUID, now: datetime) -> CockpitProjectionRunResult:
        with self._session_factory() as session:
            message = session.get(OutboxMessageRecord, message_id)
            if message is None or message.topic != COCKPIT_PROJECTION_TOPIC:
                return CockpitProjectionRunResult(skipped=1)
            event = _safe_event(message.payload_json, tenant_id=message.tenant_id)
            if event is None:
                return self._fail(message_id, now, "INVALID_COCKPIT_EVENT_PAYLOAD")
            if self._projection is None:
                return self._not_configured(message_id, now)
            tenant_id = message.tenant_id

        try:
            self._projection.apply(tenant_id=tenant_id, **event)
        except (CockpitProjectionDeliveryError, OSError, ValueError):
            return self._retry(message_id, now, "COCKPIT_PROJECTION_DELIVERY_FAILED")
        return self._publish(message_id, now)

    def _publish(self, message_id: UUID, now: datetime) -> CockpitProjectionRunResult:
        with self._session_factory.begin() as session:
            message = session.get(OutboxMessageRecord, message_id, with_for_update=True)
            if message is None or message.status == "PUBLISHED":
                return CockpitProjectionRunResult(skipped=1)
            message.status = "PUBLISHED"
            message.published_at = now
            message.next_attempt_at = None
            message.last_error_code = None
        self._metrics.record(status="PUBLISHED")
        return CockpitProjectionRunResult(delivered=1)

    def _not_configured(self, message_id: UUID, now: datetime) -> CockpitProjectionRunResult:
        with self._session_factory.begin() as session:
            message = session.get(OutboxMessageRecord, message_id, with_for_update=True)
            if message is None or message.status == "PUBLISHED":
                return CockpitProjectionRunResult(skipped=1)
            message.status = "NOT_CONFIGURED"
            message.next_attempt_at = None
            message.last_error_code = "COCKPIT_PROJECTION_NOT_CONFIGURED"
        self._metrics.record(status="NOT_CONFIGURED")
        return CockpitProjectionRunResult(not_configured=1)

    def _fail(self, message_id: UUID, now: datetime, error_code: str) -> CockpitProjectionRunResult:
        with self._session_factory.begin() as session:
            message = session.get(OutboxMessageRecord, message_id, with_for_update=True)
            if message is None or message.status == "PUBLISHED":
                return CockpitProjectionRunResult(skipped=1)
            message.status = "FAILED"
            message.attempt_count += 1
            message.next_attempt_at = None
            message.last_error_code = error_code
        self._metrics.record(status="FAILED")
        return CockpitProjectionRunResult(failed=1)

    def _retry(
        self, message_id: UUID, now: datetime, error_code: str
    ) -> CockpitProjectionRunResult:
        with self._session_factory.begin() as session:
            message = session.get(OutboxMessageRecord, message_id, with_for_update=True)
            if message is None or message.status == "PUBLISHED":
                return CockpitProjectionRunResult(skipped=1)
            decision = decide_retry(
                attempt_count=message.attempt_count,
                now=now,
                max_attempts=self._max_attempts,
            )
            message.status = decision.status
            message.attempt_count = decision.attempt_count
            message.next_attempt_at = decision.next_attempt_at
            message.last_error_code = error_code
        self._metrics.record(status=decision.status)
        return CockpitProjectionRunResult(
            retried=1 if decision.status == "RETRY" else 0,
            failed=1 if decision.status == "FAILED" else 0,
        )


def _safe_event(payload_json: object, *, tenant_id: UUID) -> SafeCockpitEvent | None:
    if not isinstance(payload_json, dict):
        return None
    expected = {
        "event_id",
        "event_type",
        "aggregate_type",
        "aggregate_id",
        "aggregate_revision",
        "data",
    }
    if set(payload_json) != expected:
        return None
    event_id = _uuid(payload_json["event_id"])
    aggregate_id = _uuid(payload_json["aggregate_id"])
    event_type = payload_json["event_type"]
    aggregate_type = payload_json["aggregate_type"]
    revision = payload_json["aggregate_revision"]
    data = payload_json["data"]
    if event_id is None or aggregate_id is None:
        return None
    if not isinstance(event_type, str) or event_type not in _ALLOWED_EVENT_TYPES:
        return None
    if aggregate_type != "DCE_STAGED_OBJECT" or not isinstance(revision, int) or revision < 0:
        return None
    if not isinstance(data, dict) or set(data) != _ALLOWED_DATA_FIELDS:
        return None
    if data.get("tenant_id") != str(tenant_id):
        return None
    if any(_uuid(data[field]) is None for field in ("storage_object_id", "consultation_id")):
        return None
    state = data.get("state")
    if not isinstance(state, str) or state not in _ALLOWED_STATES:
        return None
    return SafeCockpitEvent(
        event_id=event_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        aggregate_revision=revision,
        payload=dict(data),
    )


def _uuid(value: object) -> UUID | None:
    if not isinstance(value, str):
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def _merge(
    first: CockpitProjectionRunResult, second: CockpitProjectionRunResult
) -> CockpitProjectionRunResult:
    return CockpitProjectionRunResult(
        delivered=first.delivered + second.delivered,
        skipped=first.skipped + second.skipped,
        retried=first.retried + second.retried,
        failed=first.failed + second.failed,
        not_configured=first.not_configured + second.not_configured,
    )


def cockpit_projection_enabled(environ: Mapping[str, str] | None = None) -> bool:
    values = environ if environ is not None else os.environ
    return values.get("SMART_AO_COCKPIT_PROJECTION_ENABLED", "0") == "1"


def build_default_worker() -> CockpitProjectionWorker:
    if not cockpit_projection_enabled():
        raise RuntimeError("cockpit projection worker is disabled")
    database_url = os.environ["SMART_AO_DATABASE_URL"]
    engine = sa.create_engine(database_url)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    # The concrete projection adapter is deployment-specific; None is terminally visible
    # as NOT_CONFIGURED rather than silently pretending that a projection was updated.
    return CockpitProjectionWorker(session_factory=sessions, projection=None)


def main() -> None:
    if not cockpit_projection_enabled():
        print("cockpit projection worker disabled")
        return
    worker = build_default_worker()
    poll_seconds = float(os.getenv("SMART_AO_COCKPIT_PROJECTION_POLL_SECONDS", "30"))
    while True:
        worker.run_once()
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
