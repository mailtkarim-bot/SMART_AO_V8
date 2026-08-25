"""External event-bus port and HTTP adapter with no domain coupling."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request
from uuid import UUID

from app.platform.security.public_http import open_public_https


class ExternalEventBusPort(Protocol):
    def publish(
        self,
        *,
        event_id: UUID,
        tenant_id: UUID,
        topic: str,
        payload: Mapping[str, object],
    ) -> None:
        """Publish one already-validated notification."""


class ExternalEventBusDeliveryError(RuntimeError):
    """The external event bus did not acknowledge the notification."""


@dataclass(frozen=True, slots=True)
class HttpExternalEventBus:
    """Generic HTTPS adapter; no provider SDK or provider-specific contract."""

    url: str
    token: str
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        parsed = urlsplit(self.url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("external event bus URL must be HTTPS")
        if len(self.token) < 32:
            raise ValueError("external event bus token must contain at least 32 characters")
        if self.timeout_seconds <= 0 or self.timeout_seconds > 60:
            raise ValueError("external event bus timeout must be between 0 and 60 seconds")

    def publish(
        self,
        *,
        event_id: UUID,
        tenant_id: UUID,
        topic: str,
        payload: Mapping[str, object],
    ) -> None:
        body = json.dumps(
            {
                "event_id": str(event_id),
                "payload": dict(payload),
                "tenant_id": str(tenant_id),
                "topic": topic,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        signature = hmac.new(
            self.token.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()
        request = Request(
            self.url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "SMART-AO-event-bus/1",
                "X-SMART-AO-Signature": f"sha256={signature}",
            },
        )
        try:
            with open_public_https(request, timeout=self.timeout_seconds) as response:
                if response.status is None:
                    raise ValueError("external event bus response has no status")
                status = response.status
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            raise ExternalEventBusDeliveryError("external event bus delivery failed") from error
        if status < 200 or status >= 300:
            raise ExternalEventBusDeliveryError("external event bus rejected notification")


@dataclass(frozen=True, slots=True)
class InMemoryExternalEventBus:
    """Deterministic test adapter; never enabled by the production factory."""

    deliveries: list[dict[str, object]]

    def publish(
        self,
        *,
        event_id: UUID,
        tenant_id: UUID,
        topic: str,
        payload: Mapping[str, object],
    ) -> None:
        self.deliveries.append(
            {
                "event_id": str(event_id),
                "payload": dict(payload),
                "tenant_id": str(tenant_id),
                "topic": topic,
            }
        )
