"""Structured JSON logging configuration for production processes."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime


class JsonLogFormatter(logging.Formatter):
    """Emit stable operational fields without serializing arbitrary payloads."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in ("request_id", "method", "path", "status_code", "duration_ms"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_structured_logging() -> None:
    """Configure the application root logger once, preserving handler ownership."""

    root = logging.getLogger()
    if any(isinstance(handler.formatter, JsonLogFormatter) for handler in root.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
