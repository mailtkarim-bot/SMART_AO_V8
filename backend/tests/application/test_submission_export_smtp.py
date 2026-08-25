from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import app.workers.submission_export_smtp as smtp_worker_module
import pytest
from app.modules.submission.application.notifications import SUBMISSION_EXPORT_EMAIL_TOPIC
from app.workers.submission_export_smtp import (
    SubmissionExportSmtpWorker,
    _retry_delay,
    _safe_package_id,
)

NOW = datetime(2026, 8, 23, 1, 0, tzinfo=UTC)
PACKAGE_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001")


class FakeNotifier:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.calls: list[dict[str, object]] = []

    async def send_export_ready(self, *, recipient: str, package_id: UUID) -> None:
        self.calls.append({"recipient": recipient, "package_id": package_id})
        if self.failure is not None:
            raise self.failure


def _message(*, status: str = "RETRY", topic: str = SUBMISSION_EXPORT_EMAIL_TOPIC):
    return SimpleNamespace(
        id=uuid4(),
        topic=topic,
        status=status,
        payload_json={
            "submission_package_id": str(PACKAGE_ID),
            "delivery": "EXPORT_READY",
        },
        published_at=None,
        next_attempt_at=NOW,
        last_error_code=None,
        attempt_count=0,
    )


def _factory_for_message(message: SimpleNamespace | None) -> MagicMock:
    factory = MagicMock()
    read_session = MagicMock()
    read_session.get.return_value = message
    factory.return_value.__enter__.return_value = read_session
    write_session = MagicMock()
    write_session.get.return_value = message
    factory.begin.return_value.__enter__.return_value = write_session
    return factory


def test_safe_package_id_is_strict_and_source_closed() -> None:
    payload = {
        "submission_package_id": str(PACKAGE_ID),
        "delivery": "EXPORT_READY",
    }
    assert _safe_package_id(payload) == PACKAGE_ID
    assert _safe_package_id({**payload, "amount": 10}) is None
    assert _safe_package_id({**payload, "delivery": "DOWNLOAD"}) is None
    assert _safe_package_id({**payload, "submission_package_id": "not-a-uuid"}) is None
    assert _safe_package_id(None) is None


@pytest.mark.parametrize("attempt_count", [1, 2, 8, 20])
def test_smtp_retry_backoff_is_bounded(attempt_count: int) -> None:
    assert _retry_delay(attempt_count).total_seconds() <= 3600


def test_disabled_smtp_records_not_configured_without_calling_notifier() -> None:
    message = _message()
    notifier = FakeNotifier()
    worker = SubmissionExportSmtpWorker(
        session_factory=_factory_for_message(message),
        notifier=None,
        recipient=None,
    )

    result = asyncio.run(worker._process_message(message.id, NOW))

    assert result.not_configured == 1
    assert message.status == "NOT_CONFIGURED"
    assert message.published_at is None
    assert message.last_error_code == "SMTP_NOT_CONFIGURED"
    assert notifier.calls == []


def test_smtp_worker_delivers_successfully_and_publishes() -> None:
    message = _message()
    notifier = FakeNotifier()
    worker = SubmissionExportSmtpWorker(
        session_factory=_factory_for_message(message),
        notifier=notifier,
        recipient="patron@example.test",
    )

    result = asyncio.run(worker._process_message(message.id, NOW))

    assert result.delivered == 1
    assert message.status == "PUBLISHED"
    assert message.published_at == NOW
    assert notifier.calls == [{"recipient": "patron@example.test", "package_id": PACKAGE_ID}]


def test_smtp_worker_retries_delivery_failure_without_leaking_error() -> None:
    message = _message()
    worker = SubmissionExportSmtpWorker(
        session_factory=_factory_for_message(message),
        notifier=FakeNotifier(failure=RuntimeError("SMTP secret")),
        recipient="patron@example.test",
    )

    result = asyncio.run(worker._process_message(message.id, NOW))

    assert result.retried == 1
    assert message.status == "RETRY"
    assert message.attempt_count == 1
    assert message.last_error_code == "SMTP_NOTIFICATION_DELIVERY_FAILED"
    assert "SMTP secret" not in (message.last_error_code or "")
    assert message.next_attempt_at == NOW + timedelta(seconds=30)


def test_smtp_worker_retries_invalid_payload() -> None:
    message = _message()
    message.payload_json = {
        "submission_package_id": str(PACKAGE_ID),
        "delivery": "EXPORT_READY",
        "archive_sha256": "a" * 64,
    }
    worker = SubmissionExportSmtpWorker(
        session_factory=_factory_for_message(message),
        notifier=FakeNotifier(),
        recipient="patron@example.test",
    )

    result = asyncio.run(worker._process_message(message.id, NOW))

    assert result.retried == 1
    assert message.last_error_code == "INVALID_EXPORT_EMAIL_PAYLOAD"


def test_smtp_worker_claims_only_due_smtp_messages() -> None:
    message = _message(status="PENDING")
    factory = MagicMock()
    transaction = MagicMock()
    transaction.scalars.return_value = [message]
    factory.begin.return_value.__enter__.return_value = transaction
    worker = SubmissionExportSmtpWorker(
        session_factory=factory,
        notifier=None,
        recipient=None,
        lease_seconds=120,
    )

    result = worker._claim_due_messages(now=NOW)

    assert result == [message.id]
    assert message.status == "RETRY"
    assert message.next_attempt_at == NOW + timedelta(seconds=120)


def test_smtp_worker_skips_missing_or_published_messages() -> None:
    missing = SubmissionExportSmtpWorker(
        session_factory=_factory_for_message(None),
        notifier=None,
        recipient=None,
    )
    assert asyncio.run(missing._process_message(uuid4(), NOW)).skipped == 1

    published = _message(status="PUBLISHED")
    worker = SubmissionExportSmtpWorker(
        session_factory=_factory_for_message(published),
        notifier=FakeNotifier(),
        recipient="patron@example.test",
    )
    assert worker._publish(published.id, NOW).skipped == 1


def test_build_default_worker_rejects_smtp_without_tls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SMART_AO_DATABASE_URL", "postgresql://test")
    monkeypatch.setenv("SMART_AO_SMTP_ENABLED", "1")
    monkeypatch.setenv("SMART_AO_SMTP_TO", "patron@example.test")
    monkeypatch.setenv("SMART_AO_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMART_AO_SMTP_FROM", "robot@example.test")
    monkeypatch.setenv("SMART_AO_SMTP_USE_TLS", "0")
    monkeypatch.setenv("SMART_AO_SMTP_START_TLS", "0")
    monkeypatch.setattr(smtp_worker_module.sa, "create_engine", lambda url: object())

    with pytest.raises(RuntimeError, match="requires .*TLS"):
        smtp_worker_module.build_default_worker()


def test_build_default_worker_keeps_smtp_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SMART_AO_DATABASE_URL", "postgresql://test")
    monkeypatch.delenv("SMART_AO_SMTP_ENABLED", raising=False)
    factory = object()
    monkeypatch.setattr(smtp_worker_module.sa, "create_engine", lambda url: object())
    monkeypatch.setattr(smtp_worker_module, "sessionmaker", lambda bind, expire_on_commit: factory)

    worker = smtp_worker_module.build_default_worker()

    assert worker._session_factory is factory
    assert worker._notifier is None
    assert worker._recipient is None
