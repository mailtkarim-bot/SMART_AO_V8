from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.interfaces.http.routes.collaborator_work_tasks import (
    build_collaborator_work_task_router,
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
        return _actor()


def _actor() -> ActorContext:
    return ActorContext(
        actor_id=uuid4(),
        identity_id=uuid4(),
        tenant_id=uuid4(),
        membership_id=uuid4(),
        actor_kind=ActorKind.COLLABORATEUR,
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
        build_collaborator_work_task_router(
            service=service or _TaskService(),
            security_runtime=_runtime(resolver_error=resolver_error),
        )
    )
    return TestClient(app, raise_server_exceptions=False)


def _result(*, code, replayed=False):
    return SimpleNamespace(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        result_code=code,
        aggregate_refs=[
            {
                "aggregate_type": "CollaboratorTask",
                "aggregate_id": str(uuid4()),
                "aggregate_revision": 2,
            }
        ],
        event_ids=[str(uuid4())],
        replayed=replayed,
    )


def _create_payload():
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "requirement_id": str(uuid4()),
        "task_kind": "TECHNICAL_PREPARATION",
        "title": "Préparer la réponse technique",
        "objective": "Rassembler les éléments techniques validés.",
        "due_at": None,
    }


def _claim_payload():
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_revision": 1,
    }


def _result_payload():
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_revision": 2,
        "result_text": "Les pièces techniques ont été contrôlées.",
        "source_locator": "document:technique:1",
        "outcome": "RECORDED",
    }


def _complete_payload():
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_revision": 3,
    }


class _TaskService:
    def __init__(self, *, error=None, list_error=None):
        self.error = error
        self.list_error = list_error
        self.calls = 0

    def execute(self, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        names = {
            "CreateTaskFromRequirementCommand": "TASK_CREATED",
            "ClaimTaskCommand": "TASK_CLAIMED",
            "RecordTaskResultCommand": "TASK_UPDATED",
            "CompleteTaskCommand": "TASK_COMPLETED",
        }
        return _result(
            code=names[kwargs["command"].__class__.__name__],
            replayed=self.calls > 1,
        )

    def list_for_case(self, **kwargs):
        if self.list_error is not None:
            raise self.list_error
        case_id = kwargs["case_id"]
        return [
            SimpleNamespace(
                id=uuid4(),
                case_id=case_id,
                assignment_id=uuid4(),
                requirement_id=uuid4(),
                task_kind="TECHNICAL_PREPARATION",
                title="Préparer la réponse technique",
                objective="Contrôler les éléments techniques.",
                priority="HIGH",
                state="IN_PROGRESS",
                due_at=None,
                aggregate_revision=2,
            )
        ]


def _headers():
    return {"Authorization": "Bearer test-token"}


@pytest.mark.parametrize("authorization", [None, "Basic test-token", "Bearer"])
def test_work_task_route_rejects_missing_or_malformed_bearer(authorization):
    client = _client()
    headers = {} if authorization is None else {"Authorization": authorization}

    response = client.get(f"/api/v1/collaborator/cases/{uuid4()}/tasks", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_work_task_route_maps_invalid_context_to_401():
    response = _client(resolver_error=UnauthenticatedError()).get(
        f"/api/v1/collaborator/cases/{uuid4()}/tasks", headers=_headers()
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_list_tasks_returns_projection_without_financial_fields():
    case_id = uuid4()
    response = _client().get(
        f"/api/v1/collaborator/cases/{case_id}/tasks", headers=_headers()
    )

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == str(case_id)
    assert body["tasks"][0]["state"] == "IN_PROGRESS"
    assert "gross_margin_minor" not in body
    assert "total_cost_minor" not in body


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (PermissionError("ASSIGNMENT_REQUIRED"), 403, "FORBIDDEN"),
    ],
)
def test_list_tasks_maps_service_errors(error, status_code, detail):
    response = _client(service=_TaskService(list_error=error)).get(
        f"/api/v1/collaborator/cases/{uuid4()}/tasks", headers=_headers()
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_task_commands_return_201_then_200_on_replay():
    service = _TaskService()
    client = _client(service=service)
    case_id = uuid4()
    assignment_id = uuid4()
    task_id = uuid4()
    first = client.post(
        f"/api/v1/collaborator/cases/{case_id}/assignments/{assignment_id}/tasks",
        json=_create_payload(),
        headers=_headers(),
    )
    replay = client.post(
        f"/api/v1/collaborator/tasks/{task_id}/claim",
        json=_claim_payload(),
        headers=_headers(),
    )
    recorded = client.post(
        f"/api/v1/collaborator/tasks/{task_id}/results",
        json=_result_payload(),
        headers=_headers(),
    )
    completed = client.post(
        f"/api/v1/collaborator/tasks/{task_id}/complete",
        json=_complete_payload(),
        headers=_headers(),
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert recorded.status_code == 200
    assert completed.status_code == 200
    assert first.json()["result_code"] == "TASK_CREATED"
    assert replay.json()["result_code"] == "TASK_CLAIMED"
    assert recorded.json()["result_code"] == "TASK_UPDATED"
    assert completed.json()["result_code"] == "TASK_COMPLETED"


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (PermissionError("ASSIGNMENT_REQUIRED"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_KEY_REUSED"),
        (CommandInProgressError("running"), 409, "COMMAND_IN_PROGRESS"),
        (CommandExecutionError("VERSION_CONFLICT"), 422, "VERSION_CONFLICT"),
    ],
)
def test_task_commands_map_service_errors(error, status_code, detail):
    response = _client(service=_TaskService(error=error)).post(
        f"/api/v1/collaborator/tasks/{uuid4()}/complete",
        json=_complete_payload(),
        headers=_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_task_payload_rejects_financial_fields():
    response = _client().post(
        f"/api/v1/collaborator/tasks/{uuid4()}/results",
        json={**_result_payload(), "total_cost_minor": 100},
        headers=_headers(),
    )

    assert response.status_code == 422
