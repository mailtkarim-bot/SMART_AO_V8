import json
import logging
import re
import sys
from types import SimpleNamespace

from app.bootstrap.application import create_app
from app.platform.observability import logging as structured_logging
from app.platform.observability.logging import JsonLogFormatter
from fastapi.testclient import TestClient


def test_request_id_is_preserved_and_returned_on_response() -> None:
    response = TestClient(create_app()).get(
        "/healthz/live",
        headers={"X-Request-ID": "test-request-42"},
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "test-request-42"


def test_invalid_request_id_is_replaced_by_safe_generated_value() -> None:
    response = TestClient(create_app()).get(
        "/healthz/live",
        headers={"X-Request-ID": "contains spaces and\nunsafe data"},
    )

    assert response.status_code == 200
    assert re.fullmatch(r"[A-Za-z0-9]{32}", response.headers["x-request-id"])


def test_metrics_expose_transport_aggregates_without_business_payloads() -> None:
    client = TestClient(create_app())
    client.get("/healthz/live")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "smart_ao_http_requests_total" in response.text
    assert 'method="GET"' in response.text
    assert "tenant_id" not in response.text
    assert "user_id" not in response.text
    assert "amount" not in response.text
    assert "financial" not in response.text.lower()


def test_json_log_formatter_emits_only_operational_fields() -> None:
    record = logging.LogRecord(
        name="smart_ao.http",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="http request completed",
        args=(),
        exc_info=None,
    )
    record.request_id = "request-42"
    record.method = "GET"
    record.path = "/healthz/live"
    record.status_code = 200
    record.duration_ms = 1.25

    payload = json.loads(JsonLogFormatter().format(record))

    assert payload["message"] == "http request completed"
    assert payload["request_id"] == "request-42"
    assert payload["status_code"] == 200
    assert set(payload).issubset(
        {
            "timestamp",
            "level",
            "logger",
            "message",
            "request_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
        }
    )
    assert "tenant_id" not in payload
    assert "financial_amount" not in payload


def test_json_log_formatter_omits_absent_optional_fields() -> None:
    record = logging.LogRecord(
        name="smart_ao.worker",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="worker retry scheduled",
        args=(),
        exc_info=None,
    )

    payload = json.loads(JsonLogFormatter().format(record))

    assert payload["level"] == "WARNING"
    assert payload["logger"] == "smart_ao.worker"
    assert payload["message"] == "worker retry scheduled"
    assert "request_id" not in payload
    assert "method" not in payload
    assert "path" not in payload
    assert "status_code" not in payload
    assert "duration_ms" not in payload


def test_json_log_formatter_serializes_exception_without_business_fields() -> None:
    try:
        raise RuntimeError("storage unavailable")
    except RuntimeError:
        record = logging.LogRecord(
            name="smart_ao.worker",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="worker failed",
            args=(),
            exc_info=True,
        )
        record.exc_info = sys.exc_info()

    payload = json.loads(JsonLogFormatter().format(record))

    assert payload["message"] == "worker failed"
    assert "RuntimeError: storage unavailable" in payload["exception"]
    assert "tenant_id" not in payload
    assert "financial_amount" not in payload


def test_configure_structured_logging_installs_root_handler_once(monkeypatch) -> None:
    class FakeRoot:
        def __init__(self) -> None:
            self.handlers = []
            self.level = None

        def addHandler(self, handler) -> None:
            self.handlers.append(handler)

        def setLevel(self, level) -> None:
            self.level = level

    root = FakeRoot()
    monkeypatch.setattr(
        structured_logging,
        "logging",
        SimpleNamespace(
            INFO=logging.INFO,
            StreamHandler=logging.StreamHandler,
            getLogger=lambda: root,
        ),
    )

    structured_logging.configure_structured_logging()
    first_handlers = list(root.handlers)
    structured_logging.configure_structured_logging()

    assert len(first_handlers) == 1
    assert root.handlers == first_handlers
    assert isinstance(root.handlers[0].formatter, JsonLogFormatter)
    assert root.level == logging.INFO


def test_configure_structured_logging_replaces_non_json_handlers(monkeypatch) -> None:
    class FakeRoot:
        def __init__(self) -> None:
            self.handlers = [logging.StreamHandler()]
            self.level = None

        def addHandler(self, handler) -> None:
            self.handlers.append(handler)

        def setLevel(self, level) -> None:
            self.level = level

    root = FakeRoot()
    monkeypatch.setattr(
        structured_logging,
        "logging",
        SimpleNamespace(
            INFO=logging.INFO,
            StreamHandler=logging.StreamHandler,
            getLogger=lambda: root,
        ),
    )

    structured_logging.configure_structured_logging()

    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JsonLogFormatter)
    assert root.level == logging.INFO
