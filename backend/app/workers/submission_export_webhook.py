from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.platform.persistence.models import OutboxMessageRecord

EXPORT_TOPIC = "submission.package.exported"
PROCESS_NAME = "submission-export-webhook"


@dataclass(frozen=True, slots=True)
class WebhookRunResult:
    delivered: int = 0
    skipped: int = 0
    retried: int = 0


class SubmissionExportWebhookWorker:
    """Deliver export notifications without exposing financial package contents."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        webhook_url: str | None,
        webhook_secret: str | None = None,
        batch_size: int = 50,
        lease_seconds: int = 120,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._session_factory = session_factory
        self._webhook_url = webhook_url
        self._webhook_secret = webhook_secret
        self._batch_size = batch_size
        self._lease_seconds = lease_seconds
        self._timeout_seconds = timeout_seconds

    async def run_once(self, *, now: datetime | None = None) -> WebhookRunResult:
        effective_now = now or datetime.now(tz=UTC)
        message_ids = self._claim_due_messages(now=effective_now)
        result = WebhookRunResult()
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
                        OutboxMessageRecord.topic == EXPORT_TOPIC,
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

    async def _process_message(self, message_id: UUID, now: datetime) -> WebhookRunResult:
        with self._session_factory() as session:
            message = session.get(OutboxMessageRecord, message_id)
            if message is None or message.topic != EXPORT_TOPIC:
                return WebhookRunResult(skipped=1)
            payload = _safe_payload(message.payload_json)
            if payload is None:
                return self._retry(message_id, now, "INVALID_EXPORT_PAYLOAD")
            if self._webhook_url is None:
                return self._publish(message_id, now, skipped=True)
            if not self._webhook_secret:
                return self._retry(message_id, now, "EXPORT_WEBHOOK_CONFIGURATION_INVALID")
        try:
            status = await asyncio.to_thread(
                _post_json,
                self._webhook_url,
                payload,
                self._timeout_seconds,
                self._webhook_secret,
            )
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            return self._retry(message_id, now, "EXPORT_WEBHOOK_DELIVERY_FAILED")
        if status < 200 or status >= 300:
            return self._retry(message_id, now, f"EXPORT_WEBHOOK_HTTP_{status}")
        return self._publish(message_id, now)

    def _publish(
        self, message_id: UUID, now: datetime, *, skipped: bool = False
    ) -> WebhookRunResult:
        with self._session_factory.begin() as session:
            message = session.get(OutboxMessageRecord, message_id, with_for_update=True)
            if message is None or message.status == "PUBLISHED":
                return WebhookRunResult(skipped=1)
            message.status = "PUBLISHED"
            message.published_at = now
            message.next_attempt_at = None
            message.last_error_code = None
        return WebhookRunResult(skipped=1) if skipped else WebhookRunResult(delivered=1)

    def _retry(self, message_id: UUID, now: datetime, error_code: str) -> WebhookRunResult:
        with self._session_factory.begin() as session:
            message = session.get(OutboxMessageRecord, message_id, with_for_update=True)
            if message is None or message.status == "PUBLISHED":
                return WebhookRunResult(skipped=1)
            message.status = "RETRY"
            message.attempt_count += 1
            message.next_attempt_at = now + _retry_delay(message.attempt_count)
            message.last_error_code = error_code
        return WebhookRunResult(retried=1)


def _safe_payload(payload_json: object) -> dict[str, object] | None:
    if not isinstance(payload_json, dict):
        return None
    allowed = {"submission_package_id", "archive_sha256", "delivery"}
    data = {key: payload_json[key] for key in allowed if key in payload_json}
    if set(data) != allowed or data["delivery"] != "DOWNLOAD":
        return None
    if not isinstance(data["submission_package_id"], str):
        return None
    if not isinstance(data["archive_sha256"], str) or len(data["archive_sha256"]) != 64:
        return None
    return {"event_type": "submission.package.exported", "data": data}


def _post_json(
    url: str,
    payload: dict[str, object],
    timeout: float,
    webhook_secret: str | None = None,
) -> int:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("invalid webhook URL")
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    if not webhook_secret:
        raise ValueError("webhook secret is required")
    signature = hmac.new(
        webhook_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    request = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "SMART-AO-outbox/1",
            "X-SMART-AO-Signature": f"sha256={signature}",
        },
    )
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - URL scheme validated above
        return int(response.status)


def _merge(first: WebhookRunResult, second: WebhookRunResult) -> WebhookRunResult:
    return WebhookRunResult(
        delivered=first.delivered + second.delivered,
        skipped=first.skipped + second.skipped,
        retried=first.retried + second.retried,
    )


def _retry_delay(attempt_count: int) -> timedelta:
    return timedelta(seconds=min(30 * (2 ** max(attempt_count - 1, 0)), 3600))


def build_default_worker() -> SubmissionExportWebhookWorker:
    database_url = os.environ["SMART_AO_DATABASE_URL"]
    engine = sa.create_engine(database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return SubmissionExportWebhookWorker(
        session_factory=session_factory,
        webhook_url=os.getenv("SMART_AO_EXPORT_WEBHOOK_URL") or None,
        webhook_secret=os.getenv("SMART_AO_EXPORT_WEBHOOK_SECRET") or None,
        batch_size=int(os.getenv("SMART_AO_EXPORT_WEBHOOK_BATCH_SIZE", "50")),
        lease_seconds=int(os.getenv("SMART_AO_EXPORT_WEBHOOK_LEASE_SECONDS", "120")),
        timeout_seconds=float(os.getenv("SMART_AO_EXPORT_WEBHOOK_TIMEOUT_SECONDS", "10")),
    )


def main() -> None:
    worker = build_default_worker()
    poll_seconds = float(os.getenv("SMART_AO_EXPORT_WEBHOOK_POLL_SECONDS", "30"))
    while True:
        asyncio.run(worker.run_once())
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
