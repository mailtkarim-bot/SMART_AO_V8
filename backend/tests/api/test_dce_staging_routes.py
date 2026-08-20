from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.dce_staging import build_dce_staging_router
from app.platform.events.dispatcher import CommandExecutionError, IdempotencyKeyReusedError
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
        return ActorContext(
            actor_id=uuid4(), identity_id=uuid4(), tenant_id=uuid4(), membership_id=uuid4(),
            actor_kind=ActorKind.PATRON_ADMIN, membership_state=MembershipState.ACTIVE,
            capabilities=frozenset(), assigned_case_ids=frozenset(), session_id=uuid4(),
            authenticated_at=NOW, mfa_verified_at=None, correlation_id=uuid4(),
        )


@dataclass
class _Decision:
    allowed: bool
    http_status_code: int = 403
    code: str = "FORBIDDEN"


class _Policy:
    def __init__(self, decision=None):
        self.decision = decision or _Decision(True)
        self.calls = []

    def authorize(self, **kwargs):
        self.calls.append(kwargs)
        return self.decision


@dataclass
class _Target:
    tenant_id: object
    consultation_id: object
    storage_key: str
    expected_byte_size: int


class _UploadService:
    def __init__(self, *, error=None):
        self.error = error
        self.calls = []

    async def upload(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(storage_object_id=kwargs["storage_object_id"], state="CLEAN")


class _Dispatcher:
    def __init__(self, *, error=None):
        self.error = error
        self.calls = []

    def dispatch(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            command_id=uuid4(), idempotency_key=uuid4(),
            result_code="DCE_STAGING_PREPARED",
            aggregate_refs=[{"aggregate_type": "DceStagedObject", "aggregate_id": uuid4(),
                             "aggregate_revision": 1}],
            event_ids=[uuid4()], replayed=False,
        )


class _Runtime:
    def __init__(self, *, consultation_tenant=None, target=None, dispatcher=None, upload=None):
        self.consultation_tenant = consultation_tenant
        self.target = target
        self.dispatcher = dispatcher or _Dispatcher()
        self.dce_upload_service = upload or _UploadService()
        self.consultation_calls = []
        self.target_calls = []

    def get_consultation_tenant_id(self, *, consultation_id):
        self.consultation_calls.append(consultation_id)
        return self.consultation_tenant

    def get_dce_staged_object_upload_target(self, *, storage_object_id):
        self.target_calls.append(storage_object_id)
        return self.target


def _security(*, policy=None, resolver_error=None):
    return ConsultationSecurityRuntime(
        context_resolver=_Resolver(error=resolver_error), policy=policy or _Policy()
    )


def _client(*, runtime=None, policy=None, resolver_error=None):
    app = FastAPI()
    app.include_router(
        build_dce_staging_router(
            runtime=runtime or _Runtime(consultation_tenant=uuid4()),
            security_runtime=_security(policy=policy, resolver_error=resolver_error),
        )
    )
    return TestClient(app, raise_server_exceptions=False)


def _headers():
    return {"Authorization": "Bearer test-token"}


def _prepare_payload(consultation_id):
    return {
        "command_id": str(uuid4()), "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()), "consultation_id": str(consultation_id),
        "consultation_revision": 2, "original_filename": "reglement.pdf",
        "expected_byte_size": 7, "source_channel": "MANUAL_UPLOAD",
        "expires_at": (NOW + timedelta(hours=1)).isoformat(),
    }


def test_prepare_staging_returns_opaque_object_and_dispatches_server_context():
    consultation_id = uuid4()
    runtime = _Runtime(consultation_tenant=uuid4())
    response = _client(runtime=runtime).post(
        "/api/v1/dce-staged-objects", json=_prepare_payload(consultation_id), headers=_headers()
    )
    assert response.status_code == 201
    body = response.json()
    assert body["result_code"] == "DCE_STAGING_PREPARED"
    assert body["staging"]["state"] == "AWAITING_UPLOAD"
    assert body["staging"]["storage_object_id"]
    command = runtime.dispatcher.calls[0]["command"]
    assert command.consultation_id == consultation_id
    assert str(command.storage_object_id) == body["staging"]["storage_object_id"]
    assert runtime.dispatcher.calls[0]["context"].tenant_id


def test_prepare_staging_maps_missing_consultation_to_neutral_404():
    consultation_id = uuid4()
    response = _client(runtime=_Runtime(consultation_tenant=None)).post(
        "/api/v1/dce-staged-objects", json=_prepare_payload(consultation_id), headers=_headers()
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "NOT_FOUND_OR_FORBIDDEN"}


@pytest.mark.parametrize(
    ("decision", "status_code", "detail"),
    [(_Decision(False, 403, "FORBIDDEN"), 403, "FORBIDDEN"),
     (_Decision(False, 404, "NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN")],
)
def test_prepare_staging_maps_authorization_decision(decision, status_code, detail):
    response = _client(policy=_Policy(decision)).post(
        "/api/v1/dce-staged-objects", json=_prepare_payload(uuid4()), headers=_headers()
    )
    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize(
    ("error", "detail"),
    [(IdempotencyKeyReusedError("reused"), "IDEMPOTENCY_KEY_REUSED"),
     (CommandExecutionError("invalid"), "COMMAND_REJECTED")],
)
def test_prepare_staging_maps_dispatch_errors(error, detail):
    runtime = _Runtime(consultation_tenant=uuid4(), dispatcher=_Dispatcher(error=error))
    response = _client(runtime=runtime).post(
        "/api/v1/dce-staged-objects", json=_prepare_payload(uuid4()), headers=_headers()
    )
    assert response.status_code == (409 if "IDEMPOTENCY" in detail else 422)
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize("authorization", [None, "Basic test-token", "Bearer"])
def test_staging_routes_reject_missing_or_malformed_bearer(authorization):
    client = _client()
    headers = {} if authorization is None else {"Authorization": authorization}
    response = client.post(
        "/api/v1/dce-staged-objects", json=_prepare_payload(uuid4()), headers=headers
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_staging_routes_map_invalid_context_to_401():
    response = _client(resolver_error=UnauthenticatedError()).post(
        "/api/v1/dce-staged-objects", json=_prepare_payload(uuid4()), headers=_headers()
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_upload_requires_idempotency_header_and_does_not_resolve_target():
    runtime = _Runtime(target=_Target(uuid4(), uuid4(), "dce/key", 7))
    response = _client(runtime=runtime).put(
        f"/api/v1/dce-staged-objects/{uuid4()}/content",
        content=b"payload", headers={**_headers(), "content-type": "application/octet-stream"},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "IDEMPOTENCY_KEY_REQUIRED"}
    assert not runtime.target_calls


def test_upload_returns_clean_state_and_forwards_binary_stream():
    storage_id = uuid4()
    target = _Target(uuid4(), uuid4(), "dce/key", 7)
    upload = _UploadService()
    runtime = _Runtime(target=target, upload=upload)
    response = _client(runtime=runtime).put(
        f"/api/v1/dce-staged-objects/{storage_id}/content",
        content=b"payload",
        headers={**_headers(), "Idempotency-Key": str(uuid4()),
                 "content-type": "application/octet-stream", "content-length": "7"},
    )
    assert response.status_code == 200
    assert response.json() == {"storage_object_id": str(storage_id), "state": "CLEAN"}
    assert upload.calls[0]["storage_key"] == "dce/key"
    assert upload.calls[0]["content_length"] == 7


@pytest.mark.parametrize(
    ("content_type", "status_code", "detail"),
    [("application/json", 415, "BINARY_STREAM_REQUIRED"),
     ("multipart/form-data; boundary=x", 415, "BINARY_STREAM_REQUIRED")],
)
def test_upload_rejects_non_binary_content_types(content_type, status_code, detail):
    runtime = _Runtime(target=_Target(uuid4(), uuid4(), "dce/key", 7))
    response = _client(runtime=runtime).put(
        f"/api/v1/dce-staged-objects/{uuid4()}/content",
        content=b"payload", headers={**_headers(), "Idempotency-Key": str(uuid4()),
                 "content-type": content_type},
    )
    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize("content_length", ["abc", "-1"])
def test_upload_rejects_invalid_content_length(content_length):
    runtime = _Runtime(target=_Target(uuid4(), uuid4(), "dce/key", 7))
    response = _client(runtime=runtime).put(
        f"/api/v1/dce-staged-objects/{uuid4()}/content",
        content=b"payload", headers={**_headers(), "Idempotency-Key": str(uuid4()),
                 "content-type": "application/octet-stream", "content-length": content_length},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "INVALID_CONTENT_LENGTH"}


def test_upload_maps_missing_target_to_neutral_404():
    response = _client(runtime=_Runtime(target=None)).put(
        f"/api/v1/dce-staged-objects/{uuid4()}/content",
        content=b"payload", headers={**_headers(), "Idempotency-Key": str(uuid4()),
                 "content-type": "application/octet-stream"},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "NOT_FOUND_OR_FORBIDDEN"}
