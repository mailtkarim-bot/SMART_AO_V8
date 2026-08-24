"""Read-only BOAMP Explore API adapter with a deliberately small field allowlist."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from app.modules.market_watch.application.ports import BoampNotice, PublicNoticeSearchPort

BOAMP_RECORDS_URL = "https://www.boamp.fr/api/explore/v2.1/catalog/datasets/boamp/records"
_ALLOWED_FIELDS = (
    "idweb",
    "objet",
    "dateparution",
    "datelimitereponse",
    "code_departement",
    "type_marche",
    "etat",
)


class BoampRegistryUnavailable(RuntimeError):
    """The public notice source could not safely answer a search."""


class BoampReadOnlySearch(PublicNoticeSearchPort):
    """Search public notices without returning BOAMP rich or financial fields."""

    def __init__(
        self,
        *,
        base_url: str = BOAMP_RECORDS_URL,
        timeout_seconds: float = 5.0,
        client: Any | None = None,
    ) -> None:
        if not base_url.startswith("https://"):
            raise ValueError("BOAMP endpoint must use HTTPS")
        if timeout_seconds <= 0 or timeout_seconds > 30:
            raise ValueError("BOAMP timeout must be between 0 and 30 seconds")
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._client = client or _build_http_client(timeout_seconds=timeout_seconds)

    def search(self, *, text: str, limit: int = 20, offset: int = 0) -> tuple[BoampNotice, ...]:
        normalized_text = _validate_search_text(text)
        if not 1 <= limit <= 100:
            raise ValueError("BOAMP limit must be between 1 and 100")
        if not 0 <= offset <= 100_000:
            raise ValueError("BOAMP offset is out of bounds")
        params = {
            "select": ",".join(_ALLOWED_FIELDS),
            "where": f"search(objet, {json.dumps(normalized_text, ensure_ascii=False)})",
            "order_by": "dateparution DESC",
            "limit": str(limit),
            "offset": str(offset),
            "lang": "fr",
        }
        try:
            response = self._client.get(
                self._base_url,
                params=params,
                timeout=self._timeout_seconds,
            )
        except Exception as exc:
            raise BoampRegistryUnavailable("BOAMP source unavailable") from exc
        if response.status_code == 429 or response.status_code >= 500:
            raise BoampRegistryUnavailable("BOAMP source refused or failed")
        if response.status_code != 200:
            raise BoampRegistryUnavailable("BOAMP source returned an unexpected status")
        try:
            payload = response.json()
            results = payload["results"]
            if not isinstance(results, list):
                raise TypeError("results is not a list")
            return tuple(_parse_notice(item) for item in results)
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise BoampRegistryUnavailable("BOAMP response invalid") from exc


def _build_http_client(*, timeout_seconds: float) -> Any:
    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError("connectors extra is not installed") from exc
    return httpx.Client(timeout=timeout_seconds, follow_redirects=False)


def _validate_search_text(text: str) -> str:
    normalized = " ".join(text.split())
    if not normalized or len(normalized) > 200:
        raise ValueError("BOAMP search text must contain between 1 and 200 characters")
    if any(ord(char) < 32 for char in normalized):
        raise ValueError("BOAMP search text contains a control character")
    return normalized


def _parse_notice(item: object) -> BoampNotice:
    if not isinstance(item, dict):
        raise TypeError("BOAMP result is not an object")
    notice_id = item.get("idweb")
    if not isinstance(notice_id, str) or not notice_id.strip():
        raise ValueError("BOAMP result has no notice id")
    title = item.get("objet")
    publication = item.get("dateparution")
    deadline = item.get("datelimitereponse")
    departments = item.get("code_departement")
    market_types = item.get("type_marche")
    status = item.get("etat")
    return BoampNotice(
        notice_id=notice_id,
        title=title if isinstance(title, str) else None,
        publication_date=(
            date.fromisoformat(publication) if isinstance(publication, str) else None
        ),
        response_deadline=(
            datetime.fromisoformat(deadline) if isinstance(deadline, str) else None
        ),
        department_codes=_string_tuple(departments),
        market_types=_string_tuple(market_types),
        status=status if isinstance(status, str) else None,
    )


def _string_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError("BOAMP list field is invalid")
    return tuple(value)
