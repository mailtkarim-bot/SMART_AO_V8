"""SMTP outbox worker for bounded submission-export notifications."""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.submission.application.notifications import SUBMISSION_EXPORT_EMAIL_TOPIC
from app.modules.submission.infrastructure.smtp_notifications import (
    AioSmtpSubmissionExportNotifier,
    SmtpNotificationUnavailable,
)
from app.platform.persistence.models import OutboxMessageRecord

PROCESS_NAME = "submission-export-smtp"


@dataclass(frozen=True, slots=True)
class SmtpRunResult:
    delivered: int = 0
    skipped: int = 0
    retried: int = 0


class SubmissionExportSmtpWorker:
    """Deliver minimal export-ready emails from a dedicated outbox topic."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        notifier,
        recipient: str | None,
        batch_size: int = 50,
        lease_seconds: int = 120,
    ) -> None:
        self._session_factory = session_factory
        self._notifier = notifier
        self._recipient = recipient.strip() if recipient else None
        self._batch_size = batch_size
        self._lease_seconds = lease_seconds

    async def run_once(self, *, now: datetime | None = None) -> SmtpRunResult:
        effective_now = now or datetime.now(tz=UTC)
        message_ids = self._claim_due_messages(now=effective_now)
        result = SmtpRunResult()
        for message_id in message_ids:
            result = _merge(result, await self._process_message(message_id, effective_now))
        return result

    def _claim_due_messages(self, *, now: datetime) -> list[UUID]:
        lease_until = now + timedelta(seconds=self._lease_seconds)
        with self._session_factory.begin() as session:
            messages = list(
                session.scalars(
                    sa.select(OutboxMessageRecord)
                    .where(
                        OutboxMessageRecord.topic == SUBMISSION_EXPORT_EMAIL_TOPIC,
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

    async def _process_message(self, message_id: UUID, now: datetime) -> SmtpRunResult:
        with self._session_factory() as session:
            message = session.get(OutboxMessageRecord, message_id)
            if message is None or message.topic != SUBMISSION_EXPORT_EMAIL_TOPIC:
                return SmtpRunResult(skipped=1)
            package_id = _safe_package_id(message.payload_json)
            if package_id is None:
                return self._retry(message_id, now, "INVALID_EXPORT_EMAIL_PAYLOAD")
            if self._notifier is None or self._recipient is None:
                return self._publish(message_id, now, skipped=True)
        try:
            await self._notifier.send_export_ready(
                recipient=self._recipient,
                package_id=package_id,
            )
        except (SmtpNotificationUnavailable, RuntimeError, ValueError):
            return self._retry(message_id, now, "SMTP_NOTIFICATION_DELIVERY_FAILED")
        return self._publish(message_id, now)

    def _publish(
        self, message_id: UUID, now: datetime, *, skipped: bool = False
    ) -> SmtpRunResult:
        with self._session_factory.begin() as session:
            message = session.get(OutboxMessageRecord, message_id, with_for_update=True)
            if message is None or message.status == "PUBLISHED":
                return SmtpRunResult(skipped=1)
            message.status = "PUBLISHED"
            message.published_at = now
            message.next_attempt_at = None
            message.last_error_code = None
        return SmtpRunResult(skipped=1) if skipped else SmtpRunResult(delivered=1)

    def _retry(self, message_id: UUID, now: datetime, error_code: str) -> SmtpRunResult:
        with self._session_factory.begin() as session:
            message = session.get(OutboxMessageRecord, message_id, with_for_update=True)
            if message is None or message.status == "PUBLISHED":
                return SmtpRunResult(skipped=1)
            message.status = "RETRY"
            message.attempt_count += 1
            message.next_attempt_at = now + _retry_delay(message.attempt_count)
            message.last_error_code = error_code
        return SmtpRunResult(retried=1)


def _safe_package_id(payload_json: object) -> UUID | None:
    if not isinstance(payload_json, dict):
        return None
    if set(payload_json) != {"submission_package_id", "delivery"}:
        return None
    if payload_json.get("delivery") != "EXPORT_READY":
        return None
    value = payload_json.get("submission_package_id")
    if not isinstance(value, str):
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def _merge(first: SmtpRunResult, second: SmtpRunResult) -> SmtpRunResult:
    return SmtpRunResult(
        delivered=first.delivered + second.delivered,
        skipped=first.skipped + second.skipped,
        retried=first.retried + second.retried,
    )


def _retry_delay(attempt_count: int) -> timedelta:
    return timedelta(seconds=min(30 * (2 ** max(attempt_count - 1, 0)), 3600))


def build_default_worker() -> SubmissionExportSmtpWorker:
    database_url = os.environ["SMART_AO_DATABASE_URL"]
    engine = sa.create_engine(database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    enabled = os.getenv("SMART_AO_SMTP_ENABLED", "0") == "1"
    notifier = None
    recipient = None
    if enabled:
        recipient = os.getenv("SMART_AO_SMTP_TO", "").strip()
        if not recipient:
            raise RuntimeError("SMART_AO_SMTP_TO is required when SMTP is enabled")
        notifier = AioSmtpSubmissionExportNotifier(
            hostname=os.environ["SMART_AO_SMTP_HOST"],
            port=int(os.getenv("SMART_AO_SMTP_PORT", "587")),
            sender=os.environ["SMART_AO_SMTP_FROM"],
            username=os.getenv("SMART_AO_SMTP_USERNAME") or None,
            password=os.getenv("SMART_AO_SMTP_PASSWORD") or None,
            use_tls=os.getenv("SMART_AO_SMTP_USE_TLS", "0") == "1",
            start_tls=_optional_bool(os.getenv("SMART_AO_SMTP_START_TLS")),
            timeout_seconds=float(os.getenv("SMART_AO_SMTP_TIMEOUT_SECONDS", "10")),
        )
    return SubmissionExportSmtpWorker(
        session_factory=session_factory,
        notifier=notifier,
        recipient=recipient,
        batch_size=int(os.getenv("SMART_AO_SMTP_BATCH_SIZE", "50")),
        lease_seconds=int(os.getenv("SMART_AO_SMTP_LEASE_SECONDS", "120")),
    )


def _optional_bool(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    if value not in {"0", "1"}:
        raise ValueError("SMTP boolean settings must be 0 or 1")
    return value == "1"


def main() -> None:
    worker = build_default_worker()
    poll_seconds = float(os.getenv("SMART_AO_SMTP_POLL_SECONDS", "30"))
    while True:
        asyncio.run(worker.run_once())
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
