import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.error import URLError
from uuid import uuid4

import app.platform.security.public_http as public_http
import app.workers.submission_export_webhook as webhook_module
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


def _message(
    *, topic: str = "submission.package.exported", status: str = "RETRY"
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        topic=topic,
        status=status,
        payload_json={
            "submission_package_id": str(uuid4()),
            "archive_sha256": "a" * 64,
            "delivery": "DOWNLOAD",
        },
        published_at=None,
        next_attempt_at=NOW,
        last_error_code=None,
        attempt_count=0,
    )


def _factory_for_message(message: SimpleNamespace) -> MagicMock:
    factory = MagicMock()
    read_session = MagicMock()
    read_session.get.return_value = message
    factory.return_value.__enter__.return_value = read_session
    write_session = MagicMock()
    write_session.get.return_value = message
    factory.begin.return_value.__enter__.return_value = write_session
    return factory


def test_claim_marks_due_messages_with_a_lease() -> None:
    message = _message(status="PENDING")
    factory = MagicMock()
    transaction = MagicMock()
    transaction.scalars.return_value = [message]
    factory.begin.return_value.__enter__.return_value = transaction
    worker = SubmissionExportWebhookWorker(session_factory=factory, webhook_url=None)

    result = worker._claim_due_messages(now=NOW)

    assert result == [message.id]
    assert message.status == "RETRY"
    assert message.next_attempt_at == NOW.replace(second=0) + timedelta(seconds=120)


def test_process_skips_missing_or_wrong_topic_messages() -> None:
    missing_factory = _factory_for_message(None)
    missing_factory.return_value.__enter__.return_value.get.return_value = None
    worker = SubmissionExportWebhookWorker(session_factory=missing_factory, webhook_url=None)
    assert asyncio.run(worker._process_message(uuid4(), NOW)).skipped == 1

    wrong = _message(topic="other.topic")
    worker = SubmissionExportWebhookWorker(
        session_factory=_factory_for_message(wrong), webhook_url=None
    )
    assert asyncio.run(worker._process_message(wrong.id, NOW)).skipped == 1


def test_process_retries_invalid_payload() -> None:
    message = _message()
    message.payload_json = {"delivery": "DOWNLOAD"}
    factory = _factory_for_message(message)
    worker = SubmissionExportWebhookWorker(
        session_factory=factory,
        webhook_url="https://example.test",
        webhook_secret="test-secret",  # pragma: allowlist secret
    )

    result = asyncio.run(worker._process_message(message.id, NOW))

    assert result.retried == 1
    assert message.attempt_count == 1
    assert message.last_error_code == "INVALID_EXPORT_PAYLOAD"


def test_process_retries_non_success_webhook_response(monkeypatch: pytest.MonkeyPatch) -> None:
    message = _message()
    monkeypatch.setattr(webhook_module, "_post_json", lambda *_args: 503)
    worker = SubmissionExportWebhookWorker(
        session_factory=_factory_for_message(message),
        webhook_url="https://example.test",
        webhook_secret="test-secret",  # pragma: allowlist secret
    )

    result = asyncio.run(worker._process_message(message.id, NOW))

    assert result.retried == 1
    assert message.last_error_code == "EXPORT_WEBHOOK_HTTP_503"


def test_publish_and_retry_are_idempotent_for_already_published_message() -> None:
    message = _message(status="PUBLISHED")
    factory = _factory_for_message(message)
    worker = SubmissionExportWebhookWorker(session_factory=factory, webhook_url=None)

    assert worker._publish(message.id, NOW).skipped == 1
    assert worker._retry(message.id, NOW, "ignored").skipped == 1


def test_safe_payload_rejects_non_dict_and_invalid_field_types() -> None:
    assert _safe_payload(None) is None
    assert _safe_payload(
        {"submission_package_id": 123, "archive_sha256": "a" * 64, "delivery": "DOWNLOAD"}
    ) is None
    assert _safe_payload(
        {"submission_package_id": "id", "archive_sha256": 123, "delivery": "DOWNLOAD"}
    ) is None
    assert _safe_payload(
        {"submission_package_id": "id", "archive_sha256": "a" * 63, "delivery": "DOWNLOAD"}
    ) is None


def test_process_delivers_successful_webhook_response(monkeypatch: pytest.MonkeyPatch) -> None:
    message = _message()
    monkeypatch.setattr(webhook_module, "_post_json", lambda *_args: 204)
    worker = SubmissionExportWebhookWorker(
        session_factory=_factory_for_message(message),
        webhook_url="https://example.test",
        webhook_secret="test-secret",  # pragma: allowlist secret
    )

    result = asyncio.run(worker._process_message(message.id, NOW))

    assert result.delivered == 1
    assert message.status == "PUBLISHED"
    assert message.published_at == NOW


@pytest.mark.parametrize("error", [URLError("offline"), TimeoutError(), OSError("socket")])
def test_process_retries_delivery_exceptions(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    message = _message()

    def raise_error(*_args: object) -> int:
        raise error

    monkeypatch.setattr(webhook_module, "_post_json", raise_error)
    worker = SubmissionExportWebhookWorker(
        session_factory=_factory_for_message(message),
        webhook_url="https://example.test",
        webhook_secret="test-secret",  # pragma: allowlist secret
    )

    result = asyncio.run(worker._process_message(message.id, NOW))

    assert result.retried == 1
    assert message.last_error_code == "EXPORT_WEBHOOK_DELIVERY_FAILED"


def test_run_once_merges_results_from_claimed_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    first = _message()
    second = _message()
    factory = MagicMock()
    transaction = MagicMock()
    transaction.scalars.return_value = [first, second]
    factory.begin.return_value.__enter__.return_value = transaction
    worker = SubmissionExportWebhookWorker(session_factory=factory, webhook_url=None)
    outcomes = iter(
        [
            webhook_module.WebhookRunResult(delivered=1),
            webhook_module.WebhookRunResult(skipped=1),
        ]
    )
    async def process_message(*_args: object) -> webhook_module.WebhookRunResult:
        return next(outcomes)

    monkeypatch.setattr(worker, "_process_message", process_message)

    result = asyncio.run(worker.run_once(now=NOW))

    assert result.delivered == 1
    assert result.skipped == 1
    assert result.retried == 0


def test_publish_and_retry_skip_missing_message() -> None:
    factory = MagicMock()
    session = MagicMock()
    session.get.return_value = None
    factory.begin.return_value.__enter__.return_value = session
    worker = SubmissionExportWebhookWorker(session_factory=factory, webhook_url=None)

    assert worker._publish(uuid4(), NOW).skipped == 1
    assert worker._retry(uuid4(), NOW, "missing").skipped == 1


def test_post_json_validates_and_sends_request(monkeypatch: pytest.MonkeyPatch) -> None:
    response = MagicMock(status=202)
    context = MagicMock()
    context.__enter__.return_value = response
    captured: list[object] = []

    def fake_urlopen(request: object, timeout: float) -> MagicMock:
        captured.append(request)
        return context

    monkeypatch.setattr(webhook_module, "open_public_https", fake_urlopen)
    monkeypatch.setattr(
        public_http.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 443))],
    )
    status = _post_json("https://example.test/hook", {"event": "ok"}, 2.5, "test-secret")

    assert status == 202
    assert captured[0].get_header("X-smart-ao-signature").startswith("sha256=")


def test_post_json_rejects_missing_host() -> None:
    with pytest.raises(ValueError, match="invalid webhook URL"):
        _post_json("https:///hook", {}, 1.0)


def test_post_json_rejects_http_and_private_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="invalid webhook URL"):
        _post_json("http://example.test/hook", {}, 1.0, "test-secret")

    monkeypatch.setattr(
        public_http.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("127.0.0.1", 443))],
    )
    with pytest.raises(ValueError, match="not public"):
        _post_json("https://example.test/hook", {}, 1.0, "test-secret")


def test_post_json_rejects_dns_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_dns(*_args: object, **_kwargs: object) -> list[object]:
        raise OSError("no DNS")

    monkeypatch.setattr(public_http.socket, "getaddrinfo", fail_dns)
    with pytest.raises(ValueError, match="DNS resolution failed"):
        _post_json("https://example.test/hook", {}, 1.0, "test-secret")


def test_build_default_worker_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = object()
    factory = object()
    monkeypatch.setenv("SMART_AO_DATABASE_URL", "postgresql://test")
    monkeypatch.setenv(  # pragma: allowlist secret
        "SMART_AO_EXPORT_WEBHOOK_URL", "https://example.test/hook"
    )
    monkeypatch.setenv("SMART_AO_EXPORT_WEBHOOK_SECRET", "test-secret")  # pragma: allowlist secret
    monkeypatch.setenv("SMART_AO_EXPORT_WEBHOOK_BATCH_SIZE", "3")
    monkeypatch.setenv("SMART_AO_EXPORT_WEBHOOK_LEASE_SECONDS", "7")
    monkeypatch.setenv("SMART_AO_EXPORT_WEBHOOK_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setattr(webhook_module.sa, "create_engine", lambda url: (url, engine))
    monkeypatch.setattr(webhook_module, "sessionmaker", lambda bind, expire_on_commit: factory)

    worker = webhook_module.build_default_worker()

    assert worker._session_factory is factory
    assert worker._webhook_url == "https://example.test/hook"
    assert worker._webhook_secret == "test-secret"  # pragma: allowlist secret
    assert worker._batch_size == 3
    assert worker._lease_seconds == 7
    assert worker._timeout_seconds == 2.5


def test_main_runs_one_poll_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    worker = MagicMock()
    monkeypatch.setattr(webhook_module, "build_default_worker", lambda: worker)
    monkeypatch.setenv("SMART_AO_EXPORT_WEBHOOK_POLL_SECONDS", "0")
    monkeypatch.setattr(webhook_module.asyncio, "run", lambda coroutine: coroutine.close())

    def stop(_seconds: float) -> None:
        raise RuntimeError("stop test loop")

    monkeypatch.setattr(webhook_module.time, "sleep", stop)
    with pytest.raises(RuntimeError, match="stop test loop"):
        webhook_module.main()
