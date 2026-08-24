"""Read-only INSEE Sirene connector for enterprise verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

SIRENE_BASE_URL = "https://api.insee.fr/api-sirene/3.11"


@dataclass(frozen=True, slots=True)
class RegisteredCompany:
    siren: str
    legal_name: str | None
    active: bool | None
    activity_code: str | None
    source: str = "INSEE_SIRENE"


class CompanyRegistryPort(Protocol):
    def find_by_siren(self, *, siren: str) -> RegisteredCompany | None: ...


class ExternalRegistryUnavailable(RuntimeError):
    """The registry could not safely answer the read-only lookup."""


class InseeSireneRegistry(CompanyRegistryPort):
    """Bounded read-only Sirene client; it never mutates enterprise records."""

    def __init__(
        self,
        *,
        token: str,
        base_url: str = SIRENE_BASE_URL,
        timeout_seconds: float = 5.0,
        client: Any | None = None,
    ) -> None:
        if not token.strip():
            raise ValueError("INSEE token is required")
        if timeout_seconds <= 0 or timeout_seconds > 30:
            raise ValueError("INSEE timeout must be between 0 and 30 seconds")
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._client = client or _build_http_client(
            token=token,
            timeout_seconds=timeout_seconds,
        )

    def find_by_siren(self, *, siren: str) -> RegisteredCompany | None:
        normalized = _validate_siren(siren)
        try:
            response = self._client.get(
                f"{self._base_url}/siren/{normalized}",
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=self._timeout_seconds,
            )
        except Exception as exc:
            raise ExternalRegistryUnavailable("INSEE registry unavailable") from exc
        if response.status_code == 404:
            return None
        if response.status_code in {401, 403, 429} or response.status_code >= 500:
            raise ExternalRegistryUnavailable("INSEE registry refused or failed")
        if response.status_code != 200:
            raise ExternalRegistryUnavailable("INSEE registry returned an unexpected status")
        try:
            payload = response.json()
            unite_legale = payload["uniteLegale"]
            period = unite_legale.get("periodesUniteLegale", [{}])[0]
            legal_name = unite_legale.get("denominationUniteLegale")
            active_value = period.get("etatAdministratifUniteLegale")
            activity_code = period.get("activitePrincipaleUniteLegale")
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise ExternalRegistryUnavailable("INSEE registry response invalid") from exc
        return RegisteredCompany(
            siren=normalized,
            legal_name=legal_name if isinstance(legal_name, str) else None,
            active=_active_value(active_value),
            activity_code=activity_code if isinstance(activity_code, str) else None,
        )


def _build_http_client(*, token: str, timeout_seconds: float) -> Any:
    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError("connectors extra is not installed") from exc
    return httpx.Client(
        timeout=timeout_seconds,
        follow_redirects=False,
        headers={"Authorization": f"Bearer {token}"},
    )


def _validate_siren(siren: str) -> str:
    normalized = siren.strip()
    if len(normalized) != 9 or not normalized.isdecimal():
        raise ValueError("SIREN must contain exactly nine digits")
    return normalized


def _active_value(value: object) -> bool | None:
    if value == "A":
        return True
    if value == "C":
        return False
    return None
