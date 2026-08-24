"""Shared retry policy for durable outbox consumers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

DEFAULT_MAX_OUTBOX_ATTEMPTS = 10
MAX_OUTBOX_ATTEMPTS_LIMIT = 100


@dataclass(frozen=True, slots=True)
class RetryDecision:
    attempt_count: int
    status: str
    next_attempt_at: datetime | None


def decide_retry(
    *,
    attempt_count: int,
    now: datetime,
    max_attempts: int = DEFAULT_MAX_OUTBOX_ATTEMPTS,
) -> RetryDecision:
    """Move poison messages to FAILED after a bounded number of attempts."""

    if not 1 <= max_attempts <= MAX_OUTBOX_ATTEMPTS_LIMIT:
        raise ValueError("max_attempts must be between 1 and 100")
    next_attempt_count = attempt_count + 1
    if next_attempt_count >= max_attempts:
        return RetryDecision(
            attempt_count=next_attempt_count,
            status="FAILED",
            next_attempt_at=None,
        )
    delay_seconds = min(30 * (2 ** max(next_attempt_count - 1, 0)), 3600)
    return RetryDecision(
        attempt_count=next_attempt_count,
        status="RETRY",
        next_attempt_at=now + timedelta(seconds=delay_seconds),
    )
