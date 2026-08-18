import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.workers.submission_export_webhook import (
    SubmissionExportWebhookWorker,
    _post_json,
    _retry_delay,
    _safe_payload,
)

NOW = datetime(2026, 8, 18, 20, 0, tzinfo=UTC)


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
    assert _retry_delay(attempt_count).total_seconds() <= 3600


def test_export_webhook_payload_rejects_malformed_data() -> None:
    assert _safe_payload({"delivery": "DOWNLOAD"}) is None
    assert _safe_payload({"delivery": "DOWNLOAD", "archive_sha256": "a" * 63}) is None
    assert _safe_payload({"delivery": "UPLOAD"}) is None


def test_empty_webhook_worker_run_is_safe() -> None:
    factory = MagicMock()
    transaction = MagicMock()
    factory.begin.return_value.__enter__.return_value = transaction
    transaction.scalars.return_value = []
    worker = SubmissionExportWebhookWorker(session_factory=factory, webhook_url=None)

    result = asyncio.run(worker.run_once(now=NOW))

    assert result.delivered == 0
    assert result.skipped == 0
    assert result.retried == 0


def test_webhook_worker_skips_without_configured_endpoint_and_publishes() -> None:
    message = SimpleNamespace(
        id=uuid4(),
        topic="submission.package.exported",
        status="RETRY",
        payload_json={
            "submission_package_id": str(uuid4()),
            "archive_sha256": "a" * 64,
            "delivery": "DOWNLOAD",
        },
        published_at=None,
        next_attempt_at=NOW,
        last_error_code="old",
    )
    factory = MagicMock()
    read_session = MagicMock()
    read_session.get.return_value = message
    factory.return_value.__enter__.return_value = read_session
    write_session = MagicMock()
    write_session.get.return_value = message
    factory.begin.return_value.__enter__.return_value = write_session
    worker = SubmissionExportWebhookWorker(session_factory=factory, webhook_url=None)

    result = asyncio.run(worker._process_message(message.id, NOW))

    assert result.skipped == 1
    assert message.status == "PUBLISHED"
    assert message.last_error_code is None


def test_webhook_url_rejects_non_http_scheme() -> None:
    with pytest.raises(ValueError, match="invalid webhook URL"):
        _post_json("file:///tmp/outbox", {}, 1.0)
