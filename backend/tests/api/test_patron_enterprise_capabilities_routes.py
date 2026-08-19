from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.patron_enterprise_capabilities import (
    build_patron_enterprise_capability_router,
)
from app.platform.events.dispatcher import (
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)
from app.platform.security.authenticated_context import UnauthenticatedError
from app.platform.security.context import ActorContext, ActorKind, MembershipState
from fastapi import FastAPI
from fastapi.testclient import TestClient

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)


@dataclass
class _Resolver:
    error: Exception | None = None

    def resolve(self, *, access_token: str) -> ActorContext:
        assert access_token == "test-token"
        if self.error is not None:
            raise self.error
        return _actor()


def _actor() -> ActorContext:
    return ActorContext(
        actor_id=uuid4(),
        identity_id=uuid4(),
        tenant_id=uuid4(),
        membership_id=uuid4(),
        actor_kind=ActorKind.PATRON_ADMIN,
        membership_state=MembershipState.ACTIVE,
        capabilities=frozenset(),
        assigned_case_ids=frozenset(),
        session_id=uuid4(),
        authenticated_at=NOW,
        mfa_verified_at=None,
        correlation_id=uuid4(),
    )


def _runtime(*, resolver_error: Exception | None = None) -> ConsultationSecurityRuntime:
    return ConsultationSecurityRuntime(
        context_resolver=_Resolver(error=resolver_error), policy=SimpleNamespace()
    )


def _client(*, service=None, resolver_error=None) -> TestClient:
    app = FastAPI()
    app.include_router(
        build_patron_enterprise_capability_router(
            service=service or _CapabilityService(),
            security_runtime=_runtime(resolver_error=resolver_error),
        )
    )
    return TestClient(app, raise_server_exceptions=False)


def _result(*, replayed=False, code="OK"):
    return SimpleNamespace(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        result_code=code,
        aggregate_refs=[{"aggregate_id": str(uuid4()), "aggregate_revision": 2}],
        event_ids=[str(uuid4())],
        replayed=replayed,
    )


def _create_payload():
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "capability_kind": "QUALIFICATION",
        "name": "Qualification travaux publics",
        "summary": "Qualification active de l’entreprise.",
        "state": "ACTIVE",
    }


def _version_payload():
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_revision": 1,
        "title": "Version 2026",
        "description": "Référentiel de qualification vérifié.",
        "valid_from": NOW.isoformat(),
        "valid_until": None,
        "usage_scope": "Réponse aux appels d’offres BTP.",
        "proof_document_ids": [str(uuid4())],
    }


class _CapabilityService:
    def __init__(self, *, create_error=None, version_error=None, read_error=None):
        self.create_error = create_error
        self.version_error = version_error
        self.read_error = read_error
        self.create_calls = 0
        self.version_calls = 0

    def create_capability(self, **kwargs):
        self.create_calls += 1
        if self.create_error is not None:
            raise self.create_error
        return _result(
            replayed=self.create_calls > 1,
            code="ENTERPRISE_CAPABILITY_CREATED",
        )

    def add_version(self, **kwargs):
        self.version_calls += 1
        if self.version_error is not None:
            raise self.version_error
        return _result(
            replayed=self.version_calls > 1,
            code="ENTERPRISE_CAPABILITY_VERSION_ADDED",
        )

    def read_capabilities(self, **kwargs):
        if self.read_error is not None:
            raise self.read_error
        company_id = kwargs["company_id"]
        version = SimpleNamespace(
            version_id=uuid4(),
            version_number=1,
            title="Version 2026",
            description="Qualification vérifiée.",
            valid_from=NOW,
            valid_until=None,
            usage_scope="BTP",
            proof_document_ids=[uuid4()],
        )
        return [
            SimpleNamespace(
                capability_id=uuid4(),
                company_id=company_id,
                aggregate_revision=2,
                capability_kind="QUALIFICATION",
                name="Qualification travaux publics",
                summary="Qualification active.",
                state="ACTIVE",
                versions=[version],
            )
        ]


def _headers():
    return {"Authorization": "Bearer test-token"}


@pytest.mark.parametrize("authorization", [None, "Basic test-token", "Bearer"])
def test_enterprise_capability_routes_reject_missing_or_malformed_bearer(authorization):
    client = _client()
    headers = {} if authorization is None else {"Authorization": authorization}

    response = client.get(
        f"/api/v1/patron/enterprise/companies/{uuid4()}/capabilities",
        headers=headers,
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_enterprise_capability_routes_map_invalid_context_to_401():
    client = _client(resolver_error=UnauthenticatedError())

    response = client.post(
        f"/api/v1/patron/enterprise/companies/{uuid4()}/capabilities",
        json=_create_payload(),
        headers=_headers(),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_create_capability_returns_201_then_200_on_replay():
    service = _CapabilityService()
    client = _client(service=service)
    payload = _create_payload()
    company_id = uuid4()

    first = client.post(
        f"/api/v1/patron/enterprise/companies/{company_id}/capabilities",
        json=payload,
        headers=_headers(),
    )
    replay = client.post(
        f"/api/v1/patron/enterprise/companies/{company_id}/capabilities",
        json=payload,
        headers=_headers(),
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert first.json()["result_code"] == "ENTERPRISE_CAPABILITY_CREATED"
    assert replay.json()["replayed"] is True


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (PermissionError("PATRON_REQUIRED"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandInProgressError("running"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandExecutionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (CommandExecutionError("CAPABILITY_ALREADY_EXISTS"), 409, "CAPABILITY_ALREADY_EXISTS"),
        (CommandExecutionError("INVALID_CAPABILITY"), 422, "COMMAND_REJECTED"),
    ],
)
def test_create_capability_maps_service_errors(error, status_code, detail):
    response = _client(service=_CapabilityService(create_error=error)).post(
        f"/api/v1/patron/enterprise/companies/{uuid4()}/capabilities",
        json=_create_payload(),
        headers=_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_add_capability_version_returns_201_then_200_on_replay():
    service = _CapabilityService()
    client = _client(service=service)
    capability_id = uuid4()
    payload = _version_payload()

    first = client.post(
        f"/api/v1/patron/enterprise/capabilities/{capability_id}/versions",
        json=payload,
        headers=_headers(),
    )
    replay = client.post(
        f"/api/v1/patron/enterprise/capabilities/{capability_id}/versions",
        json=payload,
        headers=_headers(),
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert first.json()["result_code"] == "ENTERPRISE_CAPABILITY_VERSION_ADDED"
    assert replay.json()["replayed"] is True


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (PermissionError("PATRON_REQUIRED"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandInProgressError("running"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandExecutionError("PROOF_NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (CommandExecutionError("VERSION_CONFLICT"), 409, "VERSION_CONFLICT"),
        (
            CommandExecutionError("CAPABILITY_VERSION_ALREADY_EXISTS"),
            409,
            "CAPABILITY_VERSION_ALREADY_EXISTS",
        ),
        (CommandExecutionError("INVALID_VERSION"), 422, "COMMAND_REJECTED"),
    ],
)
def test_add_capability_version_maps_service_errors(error, status_code, detail):
    response = _client(service=_CapabilityService(version_error=error)).post(
        f"/api/v1/patron/enterprise/capabilities/{uuid4()}/versions",
        json=_version_payload(),
        headers=_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_read_capabilities_returns_versions_and_proof_ids():
    company_id = uuid4()
    response = _client().get(
        f"/api/v1/patron/enterprise/companies/{company_id}/capabilities",
        headers=_headers(),
    )

    assert response.status_code == 200
    body = response.json()["capabilities"][0]
    assert body["company_id"] == str(company_id)
    assert body["versions"][0]["version_number"] == 1
    assert body["versions"][0]["proof_document_ids"]


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (PermissionError("PATRON_REQUIRED"), 403, "FORBIDDEN"),
    ],
)
def test_read_capabilities_maps_permission_errors(error, status_code, detail):
    response = _client(service=_CapabilityService(read_error=error)).get(
        f"/api/v1/patron/enterprise/companies/{uuid4()}/capabilities",
        headers=_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_capability_payload_rejects_forbidden_financial_fields():
    response = _client().post(
        f"/api/v1/patron/enterprise/companies/{uuid4()}/capabilities",
        json={**_create_payload(), "gross_margin_minor": 100},
        headers=_headers(),
    )

    assert response.status_code == 422
