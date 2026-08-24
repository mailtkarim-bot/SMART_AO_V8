from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from app.interfaces.http.routes import patron_enterprise_registry as registry_route
from app.interfaces.http.routes.patron_enterprise_registry import (
    build_patron_enterprise_registry_router,
)
from app.modules.enterprise.application.registry_lookup import EnterpriseRegistryLookupService
from app.modules.enterprise.infrastructure.insee_registry import (
    ExternalRegistryUnavailable,
    RegisteredCompany,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


class FakeRegistry:
    def __init__(self, result=None, failure: Exception | None = None) -> None:
        self.result = result
        self.failure = failure
        self.calls: list[dict[str, str]] = []

    def find_by_siren(self, *, siren: str):
        self.calls.append({"siren": siren})
        if self.failure is not None:
            raise self.failure
        return self.result


class FakePolicy:
    def __init__(self, *, allowed: bool = True) -> None:
        self.allowed = allowed
        self.requests = []

    def authorize(self, *, context, request):
        self.requests.append(request)
        return SimpleNamespace(
            allowed=self.allowed,
            http_status_code=200 if self.allowed else 403,
        )


def _app(*, registry: FakeRegistry, policy: FakePolicy) -> FastAPI:
    app = FastAPI()
    app.include_router(
        build_patron_enterprise_registry_router(
            service=EnterpriseRegistryLookupService(registry=registry),
            security_runtime=SimpleNamespace(context_resolver=object(), policy=policy),
        )
    )
    return app


def _patch_context(monkeypatch) -> None:
    monkeypatch.setattr(
        registry_route,
        "_resolve_context",
        lambda *, authorization, context_resolver: SimpleNamespace(tenant_id=TENANT_ID),
    )


def test_registry_lookup_is_auth_and_source_allowlisted(monkeypatch) -> None:
    _patch_context(monkeypatch)
    registry = FakeRegistry(
        result=RegisteredCompany(
            siren="123456789",
            legal_name="Entreprise Démonstration",
            active=True,
            activity_code="4120A",
        )
    )
    policy = FakePolicy()
    response = TestClient(_app(registry=registry, policy=policy)).get(
        "/api/v1/patron/enterprise/registry/123456789"
    )

    assert response.status_code == 200
    assert response.json() == {
        "siren": "123456789",
        "legal_name": "Entreprise Démonstration",
        "active": True,
        "activity_code": "4120A",
        "source": "INSEE_SIRENE",
    }
    assert "token" not in response.text.lower()
    assert "financial" not in response.text.lower()
    assert registry.calls == [{"siren": "123456789"}]
    assert policy.requests[0].action == "enterprise.registry.read"
    assert policy.requests[0].resource.tenant_id == TENANT_ID


def test_registry_lookup_returns_404_without_persisting_missing_company(monkeypatch) -> None:
    _patch_context(monkeypatch)
    registry = FakeRegistry(result=None)
    response = TestClient(_app(registry=registry, policy=FakePolicy())).get(
        "/api/v1/patron/enterprise/registry/123456789"
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "SIREN_NOT_FOUND"}


def test_registry_lookup_maps_external_failure_to_503(monkeypatch) -> None:
    _patch_context(monkeypatch)
    response = TestClient(
        _app(
            registry=FakeRegistry(failure=ExternalRegistryUnavailable("secret")),
            policy=FakePolicy(),
        )
    ).get("/api/v1/patron/enterprise/registry/123456789")

    assert response.status_code == 503
    assert response.json() == {"detail": "EXTERNAL_REGISTRY_UNAVAILABLE"}
    assert "secret" not in response.text


def test_registry_lookup_denies_without_capability(monkeypatch) -> None:
    _patch_context(monkeypatch)
    registry = FakeRegistry(
        result=RegisteredCompany(
            siren="123456789",
            legal_name="Should not be read",
            active=True,
            activity_code=None,
        )
    )
    response = TestClient(_app(registry=registry, policy=FakePolicy(allowed=False))).get(
        "/api/v1/patron/enterprise/registry/123456789"
    )

    assert response.status_code == 403
    assert registry.calls == []


def test_registry_lookup_bounds_siren(monkeypatch) -> None:
    _patch_context(monkeypatch)
    response = TestClient(_app(registry=FakeRegistry(), policy=FakePolicy())).get(
        "/api/v1/patron/enterprise/registry/not-a-siren"
    )

    assert response.status_code == 422
