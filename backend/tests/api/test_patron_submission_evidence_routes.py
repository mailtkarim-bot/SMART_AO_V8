from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.patron_submission_evidence import (
    build_patron_submission_evidence_router,
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


def _runtime(*, resolver_error=None):
    return ConsultationSecurityRuntime(
        context_resolver=_Resolver(error=resolver_error), policy=SimpleNamespace()
    )


def _client(*, service=None, resolver_error=None):
    app = FastAPI()
    app.include_router(
        build_patron_submission_evidence_router(
            service=service or _EvidenceService(),
            security_runtime=_runtime(resolver_error=resolver_error),
        )
    )
    return TestClient(app, raise_server_exceptions=False)


def _result(*, replayed=False):
    return SimpleNamespace(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        result_code="SUBMISSION_EVIDENCE_RECORDED",
        aggregate_refs=[{"aggregate_id": str(uuid4()), "aggregate_revision": 1}],
        event_ids=[str(uuid4())],
        replayed=replayed,
    )


def _payload():
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "evidence_id": str(uuid4()),
        "evidence_type": "MANUAL_RECEIPT",
        "external_reference_hash": "a" * 64,
        "evidence_sha256": "b" * 64,
        "notes_redacted": "Référence reçue par le portail.",
    }


class _EvidenceService:
    def __init__(self, *, error=None):
        self.error = error
        self.calls = 0

    def execute(self, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return _result(replayed=self.calls > 1)


def _headers():
    return {"Authorization": "Bearer test-token"}


@pytest.mark.parametrize("authorization", [None, "Basic test-token", "Bearer"])
def test_submission_evidence_route_rejects_missing_or_malformed_bearer(authorization):
    client = _client()
    headers = {} if authorization is None else {"Authorization": authorization}

    response = client.post(
        f"/api/v1/patron/submission-packages/{uuid4()}/evidence",
        json=_payload(),
        headers=headers,
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_submission_evidence_route_maps_invalid_context_to_401():
    response = _client(resolver_error=UnauthenticatedError()).post(
        f"/api/v1/patron/submission-packages/{uuid4()}/evidence",
        json=_payload(),
        headers=_headers(),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_record_evidence_returns_201_then_200_on_replay():
    service = _EvidenceService()
    client = _client(service=service)
    package_id = uuid4()
    payload = _payload()

    first = client.post(
        f"/api/v1/patron/submission-packages/{package_id}/evidence",
        json=payload,
        headers=_headers(),
    )
    replay = client.post(
        f"/api/v1/patron/submission-packages/{package_id}/evidence",
        json=payload,
        headers=_headers(),
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert first.json()["result_code"] == "SUBMISSION_EVIDENCE_RECORDED"
    assert first.json()["external_submission"] == "NOT_PERFORMED"
    assert replay.json()["replayed"] is True


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("PATRON_REQUIRED"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandInProgressError("running"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandExecutionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (CommandExecutionError("INVALID_EVIDENCE"), 422, "COMMAND_REJECTED"),
    ],
)
def test_record_evidence_maps_service_errors(error, status_code, detail):
    response = _client(service=_EvidenceService(error=error)).post(
        f"/api/v1/patron/submission-packages/{uuid4()}/evidence",
        json=_payload(),
        headers=_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_submission_evidence_payload_rejects_raw_or_financial_fields():
    response = _client().post(
        f"/api/v1/patron/submission-packages/{uuid4()}/evidence",
        json={**_payload(), "storage_object_id": str(uuid4()), "gross_margin_minor": 100},
        headers=_headers(),
    )

    assert response.status_code == 422


def test_submission_evidence_payload_rejects_non_hex_hashes():
    payload = _payload()
    payload["evidence_sha256"] = "not-a-sha256"

    response = _client().post(
        f"/api/v1/patron/submission-packages/{uuid4()}/evidence",
        json=payload,
        headers=_headers(),
    )

    assert response.status_code == 422
