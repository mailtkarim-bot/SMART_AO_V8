from __future__ import annotations

from collections import Counter
from threading import Lock

_ALLOWED_STATUSES = frozenset({"PUBLISHED", "RETRY", "FAILED", "NOT_CONFIGURED"})


class CockpitProjectionMetrics:
    """Process-local aggregate counters safe to expose without tenant cardinality."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._statuses: Counter[str] = Counter()

    def record(self, *, status: str) -> None:
        normalized = status.upper()
        if normalized not in _ALLOWED_STATUSES:
            raise ValueError("unsupported cockpit projection status")
        with self._lock:
            self._statuses[normalized] += 1

    def render_prometheus(self) -> str:
        with self._lock:
            statuses = {status: self._statuses[status] for status in sorted(_ALLOWED_STATUSES)}
        lines = [
            "# HELP smart_ao_cockpit_projection_messages_total "
            "Outbox messages by terminal or retry status.",
            "# TYPE smart_ao_cockpit_projection_messages_total counter",
        ]
        lines.extend(
            f'smart_ao_cockpit_projection_messages_total{{status="{status}"}} {count}'
            for status, count in statuses.items()
        )
        return "\n".join(lines) + "\n"


COCKPIT_PROJECTION_METRICS = CockpitProjectionMetrics()
