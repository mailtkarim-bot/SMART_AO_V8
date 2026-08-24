from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.workers import dce_analysis

NOW = datetime(2026, 8, 23, 12, tzinfo=UTC)


class FakeAnalysisService:
    def __init__(self, *, session_factory, dispatcher) -> None:
        self.session_factory = session_factory
        self.dispatcher = dispatcher
        self.calls: list[dict[str, object]] = []

    def analyze(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            status="SUCCEEDED",
            result_code="DCE_RC_ANALYSIS_RECORDED",
            command_id="command-id",
            idempotency_key="idempotency-key",
            event_ids=("event-id",),
            aggregate_refs=({"excerpt": "must not be returned"},),
        )


def test_worker_uses_system_analysis_service_and_returns_safe_receipt(monkeypatch) -> None:
    service_instances: list[FakeAnalysisService] = []

    def fake_service(*, session_factory, dispatcher):
        service = FakeAnalysisService(
            session_factory=session_factory,
            dispatcher=dispatcher,
        )
        service_instances.append(service)
        return service

    monkeypatch.setattr(dce_analysis, "DceRcAnalysisService", fake_service)
    tenant_id = uuid4()
    dce_version_id = uuid4()
    runtime = SimpleNamespace(dispatcher=object())

    receipt = asyncio.run(
        dce_analysis.run_once(
            session_factory=object(),
            runtime=runtime,
            tenant_id=tenant_id,
            dce_version_id=dce_version_id,
            now=NOW,
        )
    )

    assert len(service_instances) == 1
    service = service_instances[0]
    assert service.dispatcher is runtime.dispatcher
    assert service.calls == [
        {
            "tenant_id": tenant_id,
            "dce_version_id": dce_version_id,
            "now": NOW,
        }
    ]
    assert receipt == {
        "status": "SUCCEEDED",
        "result_code": "DCE_RC_ANALYSIS_RECORDED",
        "command_id": "command-id",
        "idempotency_key": "idempotency-key",
        "event_count": 1,
    }
    assert "excerpt" not in receipt


def test_worker_preserves_replay_as_zero_event_receipt(monkeypatch) -> None:
    class ReplayService:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def analyze(self, **kwargs):
            return SimpleNamespace(
                status="SUCCEEDED",
                result_code="DCE_RC_ANALYSIS_ALREADY_RECORDED",
                command_id="same-command",
                idempotency_key="same-key",
                event_ids=(),
            )

    monkeypatch.setattr(dce_analysis, "DceRcAnalysisService", ReplayService)

    receipt = asyncio.run(
        dce_analysis.run_once(
            session_factory=object(),
            runtime=SimpleNamespace(dispatcher=object()),
            tenant_id=uuid4(),
            dce_version_id=uuid4(),
        )
    )

    assert receipt["result_code"] == "DCE_RC_ANALYSIS_ALREADY_RECORDED"
    assert receipt["event_count"] == 0
