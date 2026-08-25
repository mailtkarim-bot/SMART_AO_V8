from datetime import UTC, datetime

import pytest
from app.platform.events.retry_policy import decide_retry

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


@pytest.mark.process
def test_retry_policy_schedules_bounded_retry_before_terminal_attempt() -> None:
    decision = decide_retry(attempt_count=0, now=NOW, max_attempts=3)

    assert decision.attempt_count == 1
    assert decision.status == "RETRY"
    assert decision.next_attempt_at == datetime(2026, 8, 24, 12, 0, 30, tzinfo=UTC)


@pytest.mark.process
def test_retry_policy_dead_letters_on_max_attempt() -> None:
    decision = decide_retry(attempt_count=2, now=NOW, max_attempts=3)

    assert decision.attempt_count == 3
    assert decision.status == "FAILED"
    assert decision.next_attempt_at is None


@pytest.mark.process
def test_retry_policy_rejects_unbounded_configuration() -> None:
    with pytest.raises(ValueError, match="between 1 and 100"):
        decide_retry(attempt_count=0, now=NOW, max_attempts=0)
    with pytest.raises(ValueError, match="between 1 and 100"):
        decide_retry(attempt_count=0, now=NOW, max_attempts=101)
