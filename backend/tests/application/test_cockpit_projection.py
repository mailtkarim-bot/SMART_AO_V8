from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from app.platform.observability.outbox import CockpitProjectionMetrics
from app.workers.cockpit_projection import (
    COCKPIT_PROJECTION_TOPIC,
    _safe_event,
    cockpit_projection_enabled,
)

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
EVENT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
AGGREGATE_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
STORAGE_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
CONSULTATION_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


def _event_payload() -> dict[str, object]:
    return {
        "event_id": str(EVENT_ID),
        "event_type": "DCE_STAGING_SCAN_RECORDED",
        "aggregate_type": "DCE_STAGED_OBJECT",
        "aggregate_id": str(AGGREGATE_ID),
        "aggregate_revision": 0,
        "data": {
            "storage_object_id": str(STORAGE_ID),
            "tenant_id": str(TENANT_ID),
            "consultation_id": str(CONSULTATION_ID),
            "state": "SCANNED",
        },
    }


def test_safe_event_accepts_the_closed_dce_contract() -> None:
    event = _safe_event(_event_payload(), tenant_id=TENANT_ID)

    assert event is not None
    assert event["event_id"] == EVENT_ID
    assert event["aggregate_id"] == AGGREGATE_ID
    assert event["payload"] == _event_payload()["data"]
    assert COCKPIT_PROJECTION_TOPIC == "cockpit_projection"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: payload["data"].update({"title": "forbidden"}),
        lambda payload: payload.update({"sensitive": "forbidden"}),
        lambda payload: payload["data"].update({"tenant_id": str(uuid4())}),
        lambda payload: payload.update({"aggregate_revision": -1}),
    ],
)
def test_safe_event_rejects_extra_fields_wrong_tenant_and_invalid_revision(mutator) -> None:
    payload = _event_payload()
    mutator(payload)

    assert _safe_event(payload, tenant_id=TENANT_ID) is None


def test_projection_enabled_is_explicit() -> None:
    assert not cockpit_projection_enabled({})
    assert cockpit_projection_enabled({"SMART_AO_COCKPIT_PROJECTION_ENABLED": "1"})
    assert not cockpit_projection_enabled({"SMART_AO_COCKPIT_PROJECTION_ENABLED": "true"})


def test_projection_metrics_have_bounded_status_labels() -> None:
    metrics = CockpitProjectionMetrics()
    metrics.record(status="PUBLISHED")
    metrics.record(status="NOT_CONFIGURED")

    output = metrics.render_prometheus()

    assert 'status="PUBLISHED"} 1' in output
    assert 'status="NOT_CONFIGURED"} 1' in output
    assert "tenant" not in output
    with pytest.raises(ValueError, match="unsupported"):
        metrics.record(status="TENANT_123")
