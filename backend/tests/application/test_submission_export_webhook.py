from datetime import timedelta
from uuid import uuid4

import pytest
from app.workers.submission_export_webhook import _retry_delay, _safe_payload


def test_export_webhook_payload_excludes_financial_fields() -> None:
    payload = {
        "submission_package_id": str(uuid4()),
        "manifest_sha256": "a" * 64,
        "archive_sha256": "b" * 64,
        "delivery": "DOWNLOAD",
        "financial_snapshot_id": str(uuid4()),
    }

    result = _safe_payload(payload)

    assert result is not None
    assert result["data"] == {
        "submission_package_id": payload["submission_package_id"],
        "archive_sha256": "b" * 64,
        "delivery": "DOWNLOAD",
    }
    assert "manifest_sha256" not in result["data"]
    assert "financial_snapshot_id" not in result["data"]


@pytest.mark.parametrize("attempt_count", [1, 2, 8, 20])
def test_webhook_retry_backoff_is_bounded(attempt_count: int) -> None:
    assert _retry_delay(attempt_count) <= timedelta(seconds=3600)


def test_export_webhook_payload_rejects_malformed_data() -> None:
    assert _safe_payload({"delivery": "DOWNLOAD"}) is None
    assert _safe_payload({"delivery": "DOWNLOAD", "archive_sha256": "a" * 63}) is None
    assert _safe_payload({"delivery": "UPLOAD"}) is None
