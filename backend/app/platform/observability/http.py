"""Minimal process-local HTTP observability primitives.

The registry deliberately contains only aggregate transport dimensions. It must
never receive tenant identifiers, user identifiers, request bodies, or business
payloads.
"""

from __future__ import annotations

import logging
import re
import time
from collections import Counter
from threading import Lock
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_LOGGER = logging.getLogger("smart_ao.http")


class HttpMetrics:
    """Thread-safe, process-local aggregate counters for operational health."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._requests: Counter[tuple[str, str]] = Counter()
        self._errors = 0

    def record_request(self, *, method: str, status_code: int) -> None:
        with self._lock:
            self._requests[(method, str(status_code))] += 1

    def record_error(self) -> None:
        with self._lock:
            self._errors += 1

    def render_prometheus(self) -> str:
        with self._lock:
            requests = sorted(self._requests.items())
            errors = self._errors
        lines = [
            "# HELP smart_ao_http_requests_total HTTP requests by method and status.",
            "# TYPE smart_ao_http_requests_total counter",
        ]
        lines.extend(
            f'smart_ao_http_requests_total{{method="{method}",status="{status}"}} {count}'
            for (method, status), count in requests
        )
        lines.extend(
            [
                "# HELP smart_ao_http_errors_total Unhandled HTTP application errors.",
                "# TYPE smart_ao_http_errors_total counter",
                f"smart_ao_http_errors_total {errors}",
                "",
            ]
        )
        return "\n".join(lines)


HTTP_METRICS = HttpMetrics()


def _resolve_request_id(scope: Scope) -> str:
    for name, value in scope.get("headers", []):
        if name.lower() == b"x-request-id":
            candidate = value.decode("latin-1")
            if _REQUEST_ID_RE.fullmatch(candidate):
                return candidate
            break
    return uuid4().hex


class RequestObservabilityMiddleware:
    """Add a safe request correlation id and aggregate transport telemetry."""

    def __init__(self, app: ASGIApp, *, metrics: HttpMetrics = HTTP_METRICS) -> None:
        self.app = app
        self.metrics = metrics

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _resolve_request_id(scope)
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "")
        started = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            self.metrics.record_error()
            _LOGGER.exception(
                "http request failed",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                },
            )
            raise
        finally:
            self.metrics.record_request(method=method, status_code=status_code)
            _LOGGER.info(
                "http request completed",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
