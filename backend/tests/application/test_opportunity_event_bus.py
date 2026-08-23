from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.platform.events.external_bus import (
    ExternalEventBusDeliveryError,
    HttpExternalEventBus,
    InMemoryExternalEventBus,
)
from app.workers.opportunity_event_bus import (
    BOAMP_INGESTION_TOPIC,
    BOAMP_QUALIFICATION_TOPIC,
    OpportunityEventBusWorker,
    _safe_payload,
    external_event_bus_enabled,
)


class _Context:
    def __init__(self, session: _Session) -> None:
        self.session = session

    def __enter__(self) -> _Session:
        return self.session

    def __exit__(self, *_args: object) -> None:
        return None


class _Session:
    def __init__(self, message: SimpleNamespace) -> None:
        self.message = message

    def scalars(self, _statement: object) -> list[SimpleNamespace]:
        return [self.message] if self.message.status in {"PENDING", "RETRY"} else []

    def get(self, _model: object, _message_id: object, **_kwargs: object) -> SimpleNamespace:
        return self.message


class _SessionFactory:
    def __init__(self, message: SimpleNamespace) -> None:
        self.session = _Session(message)

    def begin(self) -> _Context:
        return _Context(self.session)

    def __call__(self) -> _Context:
        return _Context(self.session)


def _message(
    *,
    payload: dict[str, object] | None = None,
    topic: str = BOAMP_QUALIFICATION_TOPIC,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        event_id=uuid4(),
        tenant_id=uuid4(),
        topic=topic,
        payload_json=payload
        or {
            "qualification_id": str(uuid4()),
            "observation_id": str(uuid4()),
            "decision": "QUALIFIED",
            "reason_code": "RELEVANT_PUBLIC_SIGNAL",
        },
        status="PENDING",
        attempt_count=0,
        next_attempt_at=None,
        published_at=None,
        last_error_code=None,
        created_at=datetime(2026, 8, 23, tzinfo=UTC),
    )


def test_safe_payload_rejects_extra_fields_and_invalid_decision() -> None:
    valid = _message().payload_json
    assert _safe_payload(BOAMP_QUALIFICATION_TOPIC, valid) == valid
    assert _safe_payload(
        BOAMP_QUALIFICATION_TOPIC, {**valid, "title": "secret-rich-data"}
    ) is None
    assert _safe_payload(
        BOAMP_QUALIFICATION_TOPIC, {**valid, "decision": "AUTO_CONVERT"}
    ) is None


def test_safe_payload_accepts_minimal_ingestion_event() -> None:
    payload = {
        "ingestion_run_id": str(uuid4()),
        "observation_count": 2,
        "request_hash": "b" * 64,
    }
    assert _safe_payload(BOAMP_INGESTION_TOPIC, payload) == payload
    assert _safe_payload(BOAMP_INGESTION_TOPIC, {**payload, "title": "forbidden"}) is None


def test_in_memory_bus_records_minimal_delivery() -> None:
    deliveries: list[dict[str, object]] = []
    bus = InMemoryExternalEventBus(deliveries)
    event_id = uuid4()
    tenant_id = uuid4()
    bus.publish(
        event_id=event_id,
        tenant_id=tenant_id,
        topic=BOAMP_QUALIFICATION_TOPIC,
        payload={"decision": "QUALIFIED"},
    )
    assert deliveries == [
        {
            "event_id": str(event_id),
            "tenant_id": str(tenant_id),
            "topic": BOAMP_QUALIFICATION_TOPIC,
            "payload": {"decision": "QUALIFIED"},
        }
    ]


def test_worker_publishes_only_after_bus_acknowledgement() -> None:
    message = _message()
    deliveries: list[dict[str, object]] = []
    worker = OpportunityEventBusWorker(
        session_factory=_SessionFactory(message),
        bus=InMemoryExternalEventBus(deliveries),
        lease_seconds=10,
    )

    result = worker.run_once(now=datetime(2026, 8, 23, 12, tzinfo=UTC))

    assert result.delivered == 1
    assert message.status == "PUBLISHED"
    assert message.published_at is not None
    assert len(deliveries) == 1


def test_worker_publishes_ingestion_event_on_its_allowlisted_topic() -> None:
    message = _message(
        topic=BOAMP_INGESTION_TOPIC,
        payload={
            "ingestion_run_id": str(uuid4()),
            "observation_count": 1,
            "request_hash": "c" * 64,
        },
    )
    deliveries: list[dict[str, object]] = []
    worker = OpportunityEventBusWorker(
        session_factory=_SessionFactory(message),
        bus=InMemoryExternalEventBus(deliveries),
    )

    result = worker.run_once(now=datetime(2026, 8, 23, 12, tzinfo=UTC))

    assert result.delivered == 1
    assert deliveries[0]["topic"] == BOAMP_INGESTION_TOPIC


def test_worker_without_bus_does_not_mark_message_published() -> None:
    message = _message()
    worker = OpportunityEventBusWorker(
        session_factory=_SessionFactory(message),
        bus=None,
        lease_seconds=10,
    )

    result = worker.run_once(now=datetime(2026, 8, 23, 12, tzinfo=UTC))

    assert result.skipped == 1
    assert message.status == "RETRY"
    assert message.published_at is None


class _FailingBus:
    def publish(self, **_kwargs: object) -> None:
        raise ExternalEventBusDeliveryError("offline")


def test_worker_retries_after_external_rejection() -> None:
    message = _message()
    worker = OpportunityEventBusWorker(
        session_factory=_SessionFactory(message),
        bus=_FailingBus(),
        lease_seconds=10,
    )

    result = worker.run_once(now=datetime(2026, 8, 23, 12, tzinfo=UTC))

    assert result.retried == 1
    assert message.status == "RETRY"
    assert message.attempt_count == 1
    assert message.last_error_code == "EXTERNAL_EVENT_BUS_DELIVERY_FAILED"
    assert message.next_attempt_at > datetime(2026, 8, 23, 12, tzinfo=UTC)


def test_external_event_bus_is_disabled_by_default() -> None:
    assert external_event_bus_enabled({}) is False
    assert external_event_bus_enabled({"SMART_AO_EXTERNAL_EVENT_BUS_ENABLED": "0"}) is False
    assert external_event_bus_enabled({"SMART_AO_EXTERNAL_EVENT_BUS_ENABLED": "1"}) is True


def test_build_default_worker_requires_explicit_bus_configuration(monkeypatch) -> None:
    from app.workers import opportunity_event_bus as module

    monkeypatch.delenv("SMART_AO_EXTERNAL_EVENT_BUS_ENABLED", raising=False)
    with pytest.raises(RuntimeError, match="disabled"):
        module.build_default_worker()

    monkeypatch.setenv("SMART_AO_EXTERNAL_EVENT_BUS_ENABLED", "1")
    database_url = (
        "postgresql+psycopg://user:pass@localhost/db"  # pragma: allowlist secret
    )
    monkeypatch.setenv("SMART_AO_DATABASE_URL", database_url)
    monkeypatch.delenv("SMART_AO_EXTERNAL_EVENT_BUS_URL", raising=False)
    monkeypatch.delenv("SMART_AO_EXTERNAL_EVENT_BUS_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="requires"):
        module.build_default_worker()


def test_http_bus_requires_https_and_nontrivial_token() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        HttpExternalEventBus(url="http://bus.invalid/events", token="x" * 32)
    with pytest.raises(ValueError, match="32"):
        HttpExternalEventBus(url="https://bus.invalid/events", token="short")
