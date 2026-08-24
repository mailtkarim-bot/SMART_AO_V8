from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.patron_submission_signature import (
    build_patron_submission_signature_router,
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

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)
SECRET = "test-signature-secret-0123456789abcdef"  # pragma: allowlist secret
PROVIDER = "TEST_PROVIDER"
PACKAGE_ID = uuid4()
SIGNATURE_ID = uuid4()


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


def _result(*, replayed=False, result_code="SUBMISSION_SIGNATURE_REQUESTED"):
    return SimpleNamespace(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        result_code=result_code,
        aggregate_refs=[{"aggregate_id": str(uuid4()), "aggregate_revision": 1}],
        event_ids=[str(uuid4())],
        replayed=replayed,
    )


class _SignatureService:
    provider = PROVIDER

    def __init__(self, *, error=None):
        self.error = error
        self.calls: list[dict[str, object]] = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        command = kwargs["command"]
        return _result(
            replayed=len(self.calls) > 1,
            result_code=(
                "SUBMISSION_SIGNATURE_RECORDED"
                if command.command_type == "RecordSubmissionSignature"
                else "SUBMISSION_SIGNATURE_REQUESTED"
            ),
        )


class _ReadService:
    def __init__(self, *, error=None):
        self.error = error
        self.calls: list[dict[str, object]] = []

    def read(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return {
            "signature_id": SIGNATURE_ID,
            "submission_package_id": PACKAGE_ID,
            "case_id": uuid4(),
            "provider": PROVIDER,
            "status": "REQUESTED",
            "expected_package_version": 2,
            "revision": 1,
        }


def _client(*, service=None, read_service=None, callback_secret=SECRET, resolver_error=None):
    app = FastAPI()
    app.include_router(
        build_patron_submission_signature_router(
            service=service or _SignatureService(),
            read_service=read_service or _ReadService(),
            security_runtime=_runtime(resolver_error=resolver_error),
            callback_secret=callback_secret,
        )
    )
    return TestClient(app, raise_server_exceptions=False)


def _headers():
    return {"Authorization": "Bearer test-token"}


def _request_payload():
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "signature_id": str(SIGNATURE_ID),
        "expected_package_version": 2,
    }


def _callback_payload():
    return {
        "delivery_id": str(uuid4()),
        "submission_package_id": str(PACKAGE_ID),
        "provider": PROVIDER,
        "provider_reference_hash": "a" * 64,
        "signature_sha256": "b" * 64,
        "outcome": "SIGNED",
    }


def _signed_callback_headers(body: bytes):
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return {**_headers(), "X-Signature-Callback": f"sha256={digest}"}


def test_request_signature_requires_bearer():
    response = _client().post(
        f"/api/v1/patron/submission-packages/{PACKAGE_ID}/signatures",
        json=_request_payload(),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_request_signature_returns_201_then_200_on_replay():
    service = _SignatureService()
    client = _client(service=service)
    payload = _request_payload()
    path = f"/api/v1/patron/submission-packages/{PACKAGE_ID}/signatures"

    first = client.post(path, json=payload, headers=_headers())
    replay = client.post(path, json=payload, headers=_headers())

    assert first.status_code == 201
    assert replay.status_code == 200
    assert first.json()["result_code"] == "SUBMISSION_SIGNATURE_REQUESTED"
    assert first.json()["external_submission"] == "NOT_PERFORMED"
    assert replay.json()["replayed"] is True
    assert service.calls[0]["command"].signer_membership_id is not None
    assert service.calls[0]["command"].provider == PROVIDER


def test_signature_request_does_not_accept_provider_or_financial_fields():
    response = _client().post(
        f"/api/v1/patron/submission-packages/{PACKAGE_ID}/signatures",
        json={**_request_payload(), "provider": PROVIDER, "margin_minor": 12},
        headers=_headers(),
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("header", "status_code", "detail"),
    [
        (None, 401, "CALLBACK_UNAUTHENTICATED"),
        ("sha256=" + "0" * 64, 401, "CALLBACK_UNAUTHENTICATED"),
    ],
)
def test_callback_requires_valid_hmac(header, status_code, detail):
    body = json.dumps(_callback_payload(), separators=(",", ":")).encode()
    headers = _headers()
    if header is not None:
        headers["X-Signature-Callback"] = header

    response = _client().post(
        f"/api/v1/patron/submission-signatures/{SIGNATURE_ID}/callback",
        content=body,
        headers={**headers, "content-type": "application/json"},
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_callback_accepts_valid_hmac_and_uses_delivery_id_as_idempotency_key():
    service = _SignatureService()
    client = _client(service=service)
    body = json.dumps(_callback_payload(), separators=(",", ":")).encode()

    response = client.post(
        f"/api/v1/patron/submission-signatures/{SIGNATURE_ID}/callback",
        content=body,
        headers={**_signed_callback_headers(body), "content-type": "application/json"},
    )

    assert response.status_code == 201
    assert response.json()["result_code"] == "SUBMISSION_SIGNATURE_RECORDED"
    command = service.calls[0]["command"]
    assert command.command_id == command.idempotency_key
    assert command.submission_package_id == PACKAGE_ID


def test_callback_route_is_unavailable_without_runtime_secret():
    body = json.dumps(_callback_payload(), separators=(",", ":")).encode()

    response = _client(callback_secret="").post(
        f"/api/v1/patron/submission-signatures/{SIGNATURE_ID}/callback",
        content=body,
        headers={**_headers(), "content-type": "application/json"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "SIGNATURE_CALLBACK_UNAVAILABLE"}


def test_signature_read_is_minimal_and_does_not_return_hashes():
    response = _client().get(
        f"/api/v1/patron/submission-signatures/{SIGNATURE_ID}",
        headers=_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "REQUESTED"
    assert body["external_submission"] == "NOT_PERFORMED"
    assert "provider_reference_hash" not in body
    assert "signature_sha256" not in body
    assert "gross_margin_minor" not in body


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("PATRON_REQUIRED"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandInProgressError("running"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandExecutionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (CommandExecutionError("INVALID_PROVIDER"), 422, "COMMAND_REJECTED"),
    ],
)
def test_signature_request_maps_service_errors(error, status_code, detail):
    response = _client(service=_SignatureService(error=error)).post(
        f"/api/v1/patron/submission-packages/{PACKAGE_ID}/signatures",
        json=_request_payload(),
        headers=_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_signature_route_maps_invalid_context_to_401():
    response = _client(resolver_error=UnauthenticatedError()).get(
        f"/api/v1/patron/submission-signatures/{SIGNATURE_ID}",
        headers=_headers(),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}
