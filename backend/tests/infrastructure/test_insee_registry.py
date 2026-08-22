from __future__ import annotations

import pytest
from app.modules.enterprise.infrastructure.insee_registry import (
    ExternalRegistryUnavailable,
    InseeSireneRegistry,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.requests: list[dict[str, object]] = []

    def get(self, url: str, **kwargs):
        self.requests.append({"url": url, **kwargs})
        return self.response


def _payload() -> dict:
    return {
        "uniteLegale": {
            "denominationUniteLegale": "BATIMENT EXEMPLE",
            "periodesUniteLegale": [
                {
                    "etatAdministratifUniteLegale": "A",
                    "activitePrincipaleUniteLegale": "41.20A",
                }
            ],
        }
    }


def test_insee_lookup_is_read_only_and_normalizes_company_facts() -> None:
    client = FakeClient(FakeResponse(200, _payload()))
    registry = InseeSireneRegistry(
        token="token-not-in-repository",
        base_url="https://insee.test",
        client=client,
    )

    company = registry.find_by_siren(siren=" 123456789 ")

    assert company is not None
    assert company.siren == "123456789"
    assert company.legal_name == "BATIMENT EXEMPLE"
    assert company.active is True
    assert company.activity_code == "41.20A"
    assert client.requests[0]["url"] == "https://insee.test/siren/123456789"
    assert client.requests[0]["headers"] == {
        "Authorization": "Bearer token-not-in-repository"
    }


def test_insee_lookup_returns_none_for_unknown_siren() -> None:
    registry = InseeSireneRegistry(
        token="token",
        client=FakeClient(FakeResponse(404)),
    )

    assert registry.find_by_siren(siren="123456789") is None


@pytest.mark.parametrize("status_code", [401, 403, 429, 500, 503])
def test_insee_lookup_fails_closed_on_external_errors(status_code: int) -> None:
    registry = InseeSireneRegistry(
        token="token",
        client=FakeClient(FakeResponse(status_code)),
    )

    with pytest.raises(ExternalRegistryUnavailable):
        registry.find_by_siren(siren="123456789")


@pytest.mark.parametrize("siren", ["", "123", "12345678A"])
def test_insee_lookup_rejects_invalid_siren(siren: str) -> None:
    registry = InseeSireneRegistry(token="token", client=FakeClient(FakeResponse(200)))

    with pytest.raises(ValueError, match="SIREN"):
        registry.find_by_siren(siren=siren)


def test_insee_lookup_rejects_invalid_response() -> None:
    registry = InseeSireneRegistry(
        token="token",
        client=FakeClient(FakeResponse(200, {"unexpected": True})),
    )

    with pytest.raises(ExternalRegistryUnavailable):
        registry.find_by_siren(siren="123456789")
