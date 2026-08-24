from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_network

import pytest
from app.interfaces.http.routes.authentication import (
    _source_ip,
    _trusted_proxy_networks_from_environment,
)
from app.platform.security.rate_limit import LoginRateLimiter
from starlette.requests import Request


def _request(*, peer: str, forwarded_for: str | None = None) -> Request:
    headers = [] if forwarded_for is None else [(b"x-forwarded-for", forwarded_for.encode())]
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": headers,
            "client": (peer, 8000),
            "server": (peer, 8000),
        }
    )


@dataclass
class FakeMonotonicClock:
    current: float = 0.0

    def __call__(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


def test_source_ip_ignores_forwarded_header_from_untrusted_peer() -> None:
    request = _request(peer="198.51.100.10", forwarded_for="203.0.113.7")

    assert _source_ip(request, trusted_proxy_networks=(ip_network("172.30.0.0/24"),)) == (
        "198.51.100.10"
    )


def test_source_ip_uses_first_forwarded_address_from_trusted_proxy() -> None:
    request = _request(
        peer="172.30.0.9",
        forwarded_for="203.0.113.7, 172.30.0.8",
    )

    assert _source_ip(request, trusted_proxy_networks=(ip_network("172.30.0.0/24"),)) == (
        "203.0.113.7"
    )


def test_source_ip_fails_closed_on_invalid_forwarded_address() -> None:
    request = _request(peer="172.30.0.9", forwarded_for="not-an-ip")

    assert _source_ip(request, trusted_proxy_networks=(ip_network("172.30.0.0/24"),)) == (
        "172.30.0.9"
    )


def test_trusted_proxy_networks_parse_explicit_cidrs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMART_AO_TRUSTED_PROXY_CIDRS", "172.30.0.0/24, 2001:db8::/32")

    networks = _trusted_proxy_networks_from_environment()

    assert [str(network) for network in networks] == ["172.30.0.0/24", "2001:db8::/32"]


def test_trusted_proxy_networks_reject_invalid_cidr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMART_AO_TRUSTED_PROXY_CIDRS", "not-a-cidr")

    with pytest.raises(RuntimeError, match="valid CIDR"):
        _trusted_proxy_networks_from_environment()


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
