from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

from app.workers import dce_extraction


class FakeExtractionService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def extract(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            status="SUCCEEDED",
            result_code="DCE_EXTRACTION_RECORDED",
            command_id="command-id",
            idempotency_key="idempotency-key",
            event_ids=("event-id",),
            aggregate_refs=({"text": "must not be returned"},),
        )


class FakeStorage:
    pass


def test_worker_uses_extraction_factory_and_returns_safe_receipt(monkeypatch) -> None:
    service = FakeExtractionService()
    factory_calls: list[dict[str, object]] = []

    def fake_factory(**kwargs):
        factory_calls.append(kwargs)
        return service

    monkeypatch.setattr(dce_extraction, "build_dce_document_extraction_service", fake_factory)
    tenant_id = uuid4()
    document_id = uuid4()
    runtime = SimpleNamespace(dispatcher=object())
    storage = FakeStorage()

    receipt = asyncio.run(
        dce_extraction.run_once(
            session_factory=object(),
            runtime=runtime,
            storage=storage,
            tenant_id=tenant_id,
            dce_document_id=document_id,
        )
    )

    assert factory_calls == [
        {
            "session_factory": factory_calls[0]["session_factory"],
            "dispatcher": runtime.dispatcher,
            "storage": storage,
        }
    ]
    assert service.calls == [
        {"tenant_id": tenant_id, "dce_document_id": document_id}
    ]
    assert receipt == {
        "status": "SUCCEEDED",
        "result_code": "DCE_EXTRACTION_RECORDED",
        "command_id": "command-id",
        "idempotency_key": "idempotency-key",
        "event_count": 1,
    }
    assert "text" not in receipt


def test_worker_receipt_is_empty_event_safe(monkeypatch) -> None:
    class EmptyService:
        async def extract(self, **kwargs):
            return SimpleNamespace(
                status="SUCCEEDED",
                result_code="DCE_EXTRACTION_REPLAYED",
                command_id="same-command",
                idempotency_key="same-key",
                event_ids=(),
            )

    monkeypatch.setattr(
        dce_extraction,
        "build_dce_document_extraction_service",
        lambda **kwargs: EmptyService(),
    )

    receipt = asyncio.run(
        dce_extraction.run_once(
            session_factory=object(),
            runtime=SimpleNamespace(dispatcher=object()),
            storage=FakeStorage(),
            tenant_id=uuid4(),
            dce_document_id=uuid4(),
        )
    )

    assert receipt["result_code"] == "DCE_EXTRACTION_REPLAYED"
    assert receipt["event_count"] == 0
