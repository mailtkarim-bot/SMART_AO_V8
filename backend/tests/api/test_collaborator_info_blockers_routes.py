from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.interfaces.http.routes.collaborator_info_blockers import (
    build_collaborator_info_blocker_router,
)
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
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
        return ActorContext(
            actor_id=uuid4(), identity_id=uuid4(), tenant_id=uuid4(), membership_id=uuid4(),
            actor_kind=ActorKind.COLLABORATEUR, membership_state=MembershipState.ACTIVE,
            capabilities=frozenset(), assigned_case_ids=frozenset(), session_id=uuid4(),
            authenticated_at=NOW, mfa_verified_at=None, correlation_id=uuid4(),
        )


def _runtime(*, resolver_error=None):
    return ConsultationSecurityRuntime(
        context_resolver=_Resolver(error=resolver_error), policy=SimpleNamespace()
    )


def _client(*, service=None, resolver_error=None):
    app = FastAPI()
    app.include_router(
        build_collaborator_info_blocker_router(
            service=service or _WorkflowService(),
            security_runtime=_runtime(resolver_error=resolver_error),
        )
    )
    return TestClient(app, raise_server_exceptions=False)


def _result(*, code, replayed=False):
    return SimpleNamespace(
        command_id=uuid4(), idempotency_key=uuid4(), result_code=code,
        aggregate_refs=[{"aggregate_type": "CollaboratorTask", "aggregate_id": str(uuid4()),
                         "aggregate_revision": 2}],
        event_ids=[str(uuid4())], replayed=replayed,
    )


def _request_payload():
    return {
        "command_id": str(uuid4()), "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()), "expected_task_revision": 1,
        "request_kind": "MISSING_SOURCE", "subject": "Source manquante",
        "question": "Quelle pièce doit être fournie ?", "requested_object": "Attestation",
        "reason": "Le contrôle ne peut pas être terminé.", "priority": "HIGH", "due_at": None,
    }


def _response_payload():
    return {
        "command_id": str(uuid4()), "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()), "expected_revision": 1,
        "response_text": "La pièce a été ajoutée au dossier.",
        "source_locator": "document:attestation:1", "outcome": "ANSWERED",
    }


def _blocker_payload():
    return {
        "command_id": str(uuid4()), "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()), "expected_revision": 1,
        "blocker_kind": "MISSING_INFORMATION", "description": "Pièce obligatoire absente.",
        "source_locator": "requirement:12", "resolution_owner": "COLLABORATEUR",
    }


def _resolve_payload():
    return {
        "command_id": str(uuid4()), "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()), "expected_revision": 2,
        "resolution_note": "La pièce a été contrôlée et le blocage est levé.",
    }


class _WorkflowService:
    def __init__(self, *, error=None, read_error=None):
        self.error = error
        self.read_error = read_error
        self.calls = 0

    def execute(self, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        names = {
            "CreateInformationRequestCommand": "INFORMATION_REQUEST_CREATED",
            "RecordInformationRequestResponseCommand": "INFORMATION_REQUEST_ANSWERED",
            "DeclareTaskBlockerCommand": "TASK_BLOCKED",
            "ResolveTaskBlockerCommand": "TASK_UNBLOCKED",
        }
        return _result(code=names[kwargs["command"].__class__.__name__], replayed=self.calls > 1)

    def read_workflow(self, **kwargs):
        if self.read_error is not None:
            raise self.read_error
        task_id = kwargs["task_id"]
        request_id = uuid4()
        task = SimpleNamespace(id=task_id, state="BLOCKED", aggregate_revision=3)
        request = SimpleNamespace(
            id=request_id, task_id=task_id, request_kind="MISSING_SOURCE",
            subject="Source manquante", question="Quelle pièce ?", requested_object="Attestation",
            reason="Contrôle bloqué.", priority="HIGH", state="ANSWERED", due_at=None,
            aggregate_revision=2,
        )
        answer = SimpleNamespace(
            id=uuid4(), request_id=request_id, request_revision=2, outcome="ANSWERED",
            response_text="Pièce fournie.", source_locator="document:1", created_at=NOW,
        )
        blocker = SimpleNamespace(
            id=uuid4(), task_id=task_id, task_revision=3, blocker_kind="MISSING_INFORMATION",
            description="Pièce obligatoire absente.", source_locator="requirement:12",
            resolution_owner="COLLABORATEUR", state="OPEN", resolution_note=None, resolved_at=None,
        )
        return task, [request], [answer], [blocker]


def _headers():
    return {"Authorization": "Bearer test-token"}


@pytest.mark.parametrize("authorization", [None, "Basic test-token", "Bearer"])
def test_info_blocker_routes_reject_missing_or_malformed_bearer(authorization):
    client = _client()
    headers = {} if authorization is None else {"Authorization": authorization}
    response = client.get(f"/api/v1/collaborator/tasks/{uuid4()}/workflow", headers=headers)
    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_info_blocker_routes_map_invalid_context_to_401():
    response = _client(resolver_error=UnauthenticatedError()).post(
        f"/api/v1/collaborator/tasks/{uuid4()}/blockers",
        json=_blocker_payload(), headers=_headers(),
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_read_workflow_returns_requests_responses_and_blockers():
    task_id = uuid4()
    response = _client().get(f"/api/v1/collaborator/tasks/{task_id}/workflow", headers=_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == str(task_id)
    assert body["information_requests"][0]["responses"][0]["outcome"] == "ANSWERED"
    assert body["blockers"][0]["state"] == "OPEN"
    assert "gross_margin_minor" not in body


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [(PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
     (PermissionError("ASSIGNMENT_REQUIRED"), 403, "FORBIDDEN")],
)
def test_read_workflow_maps_service_errors(error, status_code, detail):
    response = _client(service=_WorkflowService(read_error=error)).get(
        f"/api/v1/collaborator/tasks/{uuid4()}/workflow", headers=_headers()
    )
    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_workflow_commands_cover_create_answer_block_and_resolve():
    service = _WorkflowService()
    client = _client(service=service)
    task_id = uuid4()
    request_id = uuid4()
    paths = [
        (f"/api/v1/collaborator/tasks/{task_id}/information-requests", _request_payload(),
         "INFORMATION_REQUEST_CREATED"),
        (f"/api/v1/collaborator/information-requests/{request_id}/responses", _response_payload(),
         "INFORMATION_REQUEST_ANSWERED"),
        (f"/api/v1/collaborator/tasks/{task_id}/blockers", _blocker_payload(), "TASK_BLOCKED"),
        (f"/api/v1/collaborator/tasks/{task_id}/blockers/{uuid4()}/resolve", _resolve_payload(),
         "TASK_UNBLOCKED"),
    ]
    for index, (path, payload, code) in enumerate(paths):
        response = client.post(path, json=payload, headers=_headers())
        assert response.status_code == (201 if index == 0 else 200)
        assert response.json()["result_code"] == code


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [(PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
     (PermissionError("ASSIGNMENT_REQUIRED"), 403, "FORBIDDEN"),
     (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_KEY_REUSED"),
     (CommandInProgressError("running"), 409, "COMMAND_IN_PROGRESS"),
     (CommandExecutionError("VERSION_CONFLICT"), 422, "VERSION_CONFLICT")],
)
def test_workflow_commands_map_service_errors(error, status_code, detail):
    response = _client(service=_WorkflowService(error=error)).post(
        f"/api/v1/collaborator/tasks/{uuid4()}/blockers",
        json=_blocker_payload(), headers=_headers(),
    )
    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_workflow_payload_rejects_financial_fields():
    response = _client().post(
        f"/api/v1/collaborator/tasks/{uuid4()}/blockers",
        json={**_blocker_payload(), "gross_margin_minor": 100}, headers=_headers(),
    )
    assert response.status_code == 422
