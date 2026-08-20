from __future__ import annotations

from dataclasses import dataclass

import pytest
from app.platform.security.rate_limit import LoginRateLimiter


@dataclass
class FakeMonotonicClock:
    current: float = 0.0

    def __call__(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


def test_progressive_lockout_is_bounded_and_returns_retry_after() -> None:
    clock = FakeMonotonicClock()
    limiter = LoginRateLimiter(
        max_failures=2,
        failure_window_seconds=60,
        base_lockout_seconds=5,
        max_lockout_seconds=8,
        clock=clock,
    )

    for _ in range(2):
        limiter.record_failure(namespace="login", identity="a@example.test", source_ip="10.0.0.1")

    blocked = limiter.check(
        namespace="login", identity="a@example.test", source_ip="10.0.0.1"
    )
    assert blocked.allowed is False
    assert blocked.retry_after_seconds == 5

    clock.advance(5)
    assert limiter.check(
        namespace="login", identity="a@example.test", source_ip="10.0.0.1"
    ).allowed

    limiter.record_failure(namespace="login", identity="a@example.test", source_ip="10.0.0.1")
    limiter.record_failure(namespace="login", identity="a@example.test", source_ip="10.0.0.1")
    assert limiter.check(
        namespace="login", identity="a@example.test", source_ip="10.0.0.1"
    ).retry_after_seconds == 8


def test_buckets_are_isolated_and_success_clears_only_one_bucket() -> None:
    limiter = LoginRateLimiter(max_failures=1, base_lockout_seconds=60, max_lockout_seconds=60)
    limiter.record_failure(namespace="login", identity="a@example.test", source_ip="10.0.0.1")
    limiter.record_failure(namespace="login", identity="b@example.test", source_ip="10.0.0.1")

    assert not limiter.check(
        namespace="login", identity="a@example.test", source_ip="10.0.0.1"
    ).allowed
    assert not limiter.check(
        namespace="login", identity="b@example.test", source_ip="10.0.0.1"
    ).allowed
    limiter.record_success(namespace="login", identity="a@example.test", source_ip="10.0.0.1")
    assert limiter.check(
        namespace="login", identity="a@example.test", source_ip="10.0.0.1"
    ).allowed
    assert not limiter.check(
        namespace="login", identity="b@example.test", source_ip="10.0.0.1"
    ).allowed


def test_failure_window_expires_stale_state() -> None:
    clock = FakeMonotonicClock()
    limiter = LoginRateLimiter(
        max_failures=1,
        failure_window_seconds=10,
        base_lockout_seconds=1,
        max_lockout_seconds=1,
        clock=clock,
    )
    limiter.record_failure(namespace="refresh", identity=None, source_ip="10.0.0.1")
    assert not limiter.check(namespace="refresh", identity=None, source_ip="10.0.0.1").allowed
    clock.advance(11)
    assert limiter.check(namespace="refresh", identity=None, source_ip="10.0.0.1").allowed


@pytest.mark.parametrize("name", [
    "SMART_AO_LOGIN_MAX_FAILURES",
    "SMART_AO_LOGIN_FAILURE_WINDOW_SECONDS",
    "SMART_AO_LOGIN_BASE_LOCKOUT_SECONDS",
    "SMART_AO_LOGIN_MAX_LOCKOUT_SECONDS",
])
def test_environment_values_must_be_positive_integers(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    monkeypatch.setenv(name, "0")
    with pytest.raises(RuntimeError, match="positive integer"):
        LoginRateLimiter.from_environment()
