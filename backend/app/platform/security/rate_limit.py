from __future__ import annotations

import hashlib
import os
import threading
from dataclasses import dataclass
from time import monotonic


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0


@dataclass(slots=True)
class _FailureState:
    first_failure_at: float
    last_failure_at: float
    failures: int
    locked_until: float


class LoginRateLimiter:
    """Process-local progressive limiter for login and refresh boundaries.

    The state is intentionally bounded and contains only hashed bucket keys.
    A multi-replica deployment must replace this implementation with a shared
    store; production factory rejects an invalid configuration rather than
    silently disabling the limiter.
    """

    def __init__(
        self,
        *,
        max_failures: int = 5,
        failure_window_seconds: int = 900,
        base_lockout_seconds: int = 30,
        max_lockout_seconds: int = 900,
        max_buckets: int = 100_000,
        clock=monotonic,
    ) -> None:
        if min(
            max_failures,
            failure_window_seconds,
            base_lockout_seconds,
            max_lockout_seconds,
            max_buckets,
        ) <= 0:
            raise ValueError("rate limiter settings must be positive")
        if base_lockout_seconds > max_lockout_seconds:
            raise ValueError("base lockout cannot exceed maximum lockout")
        self._max_failures = max_failures
        self._failure_window_seconds = failure_window_seconds
        self._base_lockout_seconds = base_lockout_seconds
        self._max_lockout_seconds = max_lockout_seconds
        self._max_buckets = max_buckets
        self._clock = clock
        self._states: dict[str, _FailureState] = {}
        self._lock = threading.Lock()

    @classmethod
    def from_environment(cls) -> LoginRateLimiter:
        return cls(
            max_failures=_positive_int("SMART_AO_LOGIN_MAX_FAILURES", 5),
            failure_window_seconds=_positive_int(
                "SMART_AO_LOGIN_FAILURE_WINDOW_SECONDS", 900
            ),
            base_lockout_seconds=_positive_int(
                "SMART_AO_LOGIN_BASE_LOCKOUT_SECONDS", 30
            ),
            max_lockout_seconds=_positive_int(
                "SMART_AO_LOGIN_MAX_LOCKOUT_SECONDS", 900
            ),
            max_buckets=_positive_int("SMART_AO_LOGIN_MAX_BUCKETS", 100_000),
        )

    def check(self, *, namespace: str, identity: str | None, source_ip: str) -> RateLimitDecision:
        now = self._clock()
        key = _bucket_key(namespace=namespace, identity=identity, source_ip=source_ip)
        with self._lock:
            state = self._states.get(key)
            if state is None:
                return RateLimitDecision(allowed=True)
            if state.locked_until > now:
                return RateLimitDecision(
                    allowed=False,
                    retry_after_seconds=max(1, int(state.locked_until - now)),
                )
            if now - state.last_failure_at > self._failure_window_seconds:
                self._states.pop(key, None)
        return RateLimitDecision(allowed=True)

    def record_failure(
        self, *, namespace: str, identity: str | None, source_ip: str
    ) -> None:
        now = self._clock()
        key = _bucket_key(namespace=namespace, identity=identity, source_ip=source_ip)
        with self._lock:
            state = self._states.get(key)
            if state is None or now - state.last_failure_at > self._failure_window_seconds:
                self._evict_expired(now)
                if key not in self._states and len(self._states) >= self._max_buckets:
                    oldest_key = min(
                        self._states,
                        key=lambda candidate: self._states[candidate].last_failure_at,
                    )
                    self._states.pop(oldest_key, None)
                state = _FailureState(
                    first_failure_at=now,
                    last_failure_at=now,
                    failures=0,
                    locked_until=0.0,
                )
                self._states[key] = state
            state.failures += 1
            state.last_failure_at = now
            if state.failures >= self._max_failures:
                exponent = state.failures - self._max_failures
                lockout = min(
                    self._max_lockout_seconds,
                    self._base_lockout_seconds * (2**exponent),
                )
                state.locked_until = now + lockout

    def _evict_expired(self, now: float) -> None:
        expired = [
            key
            for key, state in self._states.items()
            if now - state.last_failure_at > self._failure_window_seconds
        ]
        for key in expired:
            self._states.pop(key, None)

    def record_success(self, *, namespace: str, identity: str | None, source_ip: str) -> None:
        key = _bucket_key(namespace=namespace, identity=identity, source_ip=source_ip)
        with self._lock:
            self._states.pop(key, None)


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as error:
        raise RuntimeError(f"{name} must be a positive integer") from error
    if value <= 0:
        raise RuntimeError(f"{name} must be a positive integer")
    return value


def _bucket_key(*, namespace: str, identity: str | None, source_ip: str) -> str:
    normalized_identity = (identity or "anonymous").strip().casefold()
    normalized_ip = source_ip.strip() or "unknown"
    canonical = f"{namespace}:{normalized_identity}:{normalized_ip}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
