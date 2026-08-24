from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.patron_actions import build_patron_action_router
from app.interfaces.http.routes.patron_submission import build_patron_submission_router
from app.modules.patron_action.application.service import PatronActionProjection
from app.platform.events.dispatcher import (
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)
from app.platform.security.authenticated_context import UnauthenticatedError
from app.platform.security.context import (
    ActorContext,
    ActorKind,
    MembershipState,
)
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
    identifier = uuid4()
    return ActorContext(
        actor_id=identifier,
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
        context_resolver=_Resolver(error=resolver_error),
        policy=SimpleNamespace(),
    )


def _client(*, submission=None, actions=None, transitions=None, resolver_error=None):
    app = FastAPI()
    app.include_router(
        build_patron_submission_router(
            service=submission,
            security_runtime=_runtime(resolver_error=resolver_error),
        )
    )
    app.include_router(
        build_patron_action_router(
            service=actions,
            transition_service=transitions,
            security_runtime=_runtime(resolver_error=resolver_error),
        )
    )
    return TestClient(app, raise_server_exceptions=False)


def _result(*, replayed: bool = False, transition: bool = False):
    aggregate_id = uuid4()
    return SimpleNamespace(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        result_code=(
            "PATRON_ACTION_TRANSITIONED"
            if transition
            else "PATRON_ACTION_CREATED"
            if aggregate_id
            else "SUBMISSION_PACKAGE_PREPARED"
        ),
        aggregate_refs=[
            {"aggregate_id": str(aggregate_id), "aggregate_revision": 2}
        ],
        event_ids=[str(uuid4())],
        replayed=replayed,
    )


def _submission_payload() -> dict[str, object]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "expected_preparation_revision": 3,
    }


def _action_payload() -> dict[str, object]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "action_id": str(uuid4()),
        "case_id": str(uuid4()),
        "functional_key": "submission-review",
        "action_type": "REVIEW_PREPARATION",
        "severity": "BLOCKING",
        "title": "Contrôler la préparation",
        "why_now": "Le dossier est prêt pour revue.",
        "impact": "Une validation est nécessaire avant dépôt.",
        "recommended_action": "Ouvrir le dossier de décision.",
        "due_at": None,
        "source_refs": ["preparation-readiness"],
    }


def _transition_payload() -> dict[str, object]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "transition_id": str(uuid4()),
        "expected_revision": 2,
        "target_state": "IN_PROGRESS",
        "reason_code": "PATRON_REVIEW",
    }


class _SubmissionService:
    def __init__(self, *, prepare_error=None, export_error=None):
        self.prepare_error = prepare_error
        self.export_error = export_error
        self.prepare_calls = 0

    def prepare(self, **kwargs):
        self.prepare_calls += 1
        if self.prepare_error is not None:
            raise self.prepare_error
        return _result(replayed=self.prepare_calls > 1)

    def export(self, **kwargs):
        if self.export_error is not None:
            raise self.export_error
        return b"PK\x03\x04test-archive"


class _ActionService:
    def __init__(self, *, execute_error=None, list_error=None):
        self.execute_error = execute_error
        self.list_error = list_error
        self.execute_calls = 0

    def execute(self, **kwargs):
        self.execute_calls += 1
        if self.execute_error is not None:
            raise self.execute_error
        return _result(replayed=self.execute_calls > 1)

    def list_open(self, **kwargs):
        if self.list_error is not None:
            raise self.list_error
        return [
            PatronActionProjection(
                action_id=uuid4(),
                case_id=uuid4(),
                functional_key="submission-review",
                action_type="REVIEW_PREPARATION",
                severity="BLOCKING",
                state="OPEN",
                title="Contrôler la préparation",
                why_now="Le dossier est prêt.",
                impact="La revue est requise.",
                recommended_action="Ouvrir le dossier.",
                due_at=None,
                source_refs=("readiness",),
                aggregate_revision=1,
            )
        ]


class _TransitionService:
    def __init__(self, *, error=None):
        self.error = error
        self.calls = 0

    def execute(self, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return _result(replayed=self.calls > 1, transition=True)


@pytest.mark.parametrize("authorization", [None, "Basic test-token", "Bearer"])
def test_patron_routes_reject_missing_or_malformed_bearer(authorization):
    client = _client(
        submission=_SubmissionService(),
        actions=_ActionService(),
        transitions=_TransitionService(),
    )
    headers = {} if authorization is None else {"Authorization": authorization}

    response = client.get("/api/v1/patron/actions", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_patron_routes_map_invalid_resolved_context_to_401():
    client = _client(
        submission=_SubmissionService(),
        actions=_ActionService(),
        transitions=_TransitionService(),
        resolver_error=UnauthenticatedError(),
    )

    response = client.get(
        "/api/v1/patron/actions",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "UNAUTHENTICATED"


def test_prepare_submission_returns_201_then_200_on_replay():
    service = _SubmissionService()
    client = _client(submission=service, actions=_ActionService(), transitions=_TransitionService())
    headers = {"Authorization": "Bearer test-token"}
    package_id = uuid4()
    payload = _submission_payload()

    first = client.post(
        f"/api/v1/patron/preparation/{package_id}/submission-packages",
        json=payload,
        headers=headers,
    )
    replay = client.post(
        f"/api/v1/patron/preparation/{package_id}/submission-packages",
        json=payload,
        headers=headers,
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert service.prepare_calls == 2


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (PermissionError("PATRON_REQUIRED"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandInProgressError("running"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandExecutionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (CommandExecutionError("DCE_NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (CommandExecutionError("VERSION_CONFLICT"), 409, "VERSION_CONFLICT"),
        (CommandExecutionError("PREPARATION_BLOCKED"), 422, "COMMAND_REJECTED"),
        (CommandExecutionError("DECISION_SUBMISSION_BLOCKED"), 422, "COMMAND_REJECTED"),
    ],
)
def test_prepare_submission_maps_service_errors(error, status_code, detail):
    client = _client(
        submission=_SubmissionService(prepare_error=error),
        actions=_ActionService(),
        transitions=_TransitionService(),
    )

    response = client.post(
        f"/api/v1/patron/preparation/{uuid4()}/submission-packages",
        json=_submission_payload(),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_export_submission_returns_private_zip_headers_and_bytes():
    client = _client(
        submission=_SubmissionService(),
        actions=_ActionService(),
        transitions=_TransitionService(),
    )
    package_id = uuid4()

    response = client.get(
        f"/api/v1/patron/submission-packages/{package_id}/export",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.content.startswith(b"PK")
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["cache-control"] == "no-store"
    assert f'submission-{package_id}.zip' in response.headers["content-disposition"]


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (PermissionError("PATRON_REQUIRED"), 403, "FORBIDDEN"),
        (CommandExecutionError("MANIFEST_INVALID"), 422, "EXPORT_REJECTED"),
        (RuntimeError("SUBMISSION_EXPORT_STORAGE_NOT_CONFIGURED"), 503, "EXPORT_UNAVAILABLE"),
    ],
)
def test_export_submission_maps_service_errors(error, status_code, detail):
    client = _client(
        submission=_SubmissionService(export_error=error),
        actions=_ActionService(),
        transitions=_TransitionService(),
    )

    response = client.get(
        f"/api/v1/patron/submission-packages/{uuid4()}/export",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_list_actions_returns_projection_and_open_count():
    client = _client(
        submission=_SubmissionService(),
        actions=_ActionService(),
        transitions=_TransitionService(),
    )

    response = client.get(
        "/api/v1/patron/actions",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["open_count"] == 1
    assert response.json()["items"][0]["severity"] == "BLOCKING"


@pytest.mark.parametrize(
    "error", [PermissionError("PATRON_REQUIRED"), PermissionError("FORBIDDEN")]
)
def test_list_actions_maps_all_permission_errors_to_403(error):
    client = _client(
        submission=_SubmissionService(),
        actions=_ActionService(list_error=error),
        transitions=_TransitionService(),
    )

    response = client.get(
        "/api/v1/patron/actions",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "FORBIDDEN"}


def test_create_action_returns_201_then_200_on_replay():
    service = _ActionService()
    client = _client(
        submission=_SubmissionService(),
        actions=service,
        transitions=_TransitionService(),
    )
    headers = {"Authorization": "Bearer test-token"}
    payload = _action_payload()

    first = client.post("/api/v1/patron/actions", json=payload, headers=headers)
    replay = client.post("/api/v1/patron/actions", json=payload, headers=headers)

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert first.json()["status"] == "SUCCEEDED"


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("PATRON_REQUIRED"), 403, "PATRON_REQUIRED"),
        (PermissionError("OTHER"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_KEY_REUSED"),
        (CommandInProgressError("running"), 409, "COMMAND_IN_PROGRESS"),
        (
            CommandExecutionError("PATRON_ACTION_ALREADY_EXISTS"),
            409,
            "PATRON_ACTION_ALREADY_EXISTS",
        ),
        (CommandExecutionError("INVALID_CASE"), 422, "INVALID_CASE"),
    ],
)
def test_create_action_maps_service_errors(error, status_code, detail):
    client = _client(
        submission=_SubmissionService(),
        actions=_ActionService(execute_error=error),
        transitions=_TransitionService(),
    )

    response = client.post(
        "/api/v1/patron/actions",
        json=_action_payload(),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_transition_action_returns_201_then_200_on_replay():
    transitions = _TransitionService()
    client = _client(
        submission=_SubmissionService(),
        actions=_ActionService(),
        transitions=transitions,
    )
    action_id = uuid4()
    headers = {"Authorization": "Bearer test-token"}
    payload = _transition_payload()

    first = client.post(
        f"/api/v1/patron/actions/{action_id}/transitions",
        json=payload,
        headers=headers,
    )
    replay = client.post(
        f"/api/v1/patron/actions/{action_id}/transitions",
        json=payload,
        headers=headers,
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert first.json()["result_code"] == "PATRON_ACTION_TRANSITIONED"


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("PATRON_REQUIRED"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandInProgressError("running"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandExecutionError("VERSION_CONFLICT"), 409, "VERSION_CONFLICT"),
        (CommandExecutionError("ACTION_ALREADY_CLOSED"), 409, "ACTION_ALREADY_CLOSED"),
        (CommandExecutionError("INVALID_TRANSITION"), 422, "INVALID_TRANSITION"),
    ],
)
def test_transition_action_maps_service_errors(error, status_code, detail):
    client = _client(
        submission=_SubmissionService(),
        actions=_ActionService(),
        transitions=_TransitionService(error=error),
    )

    response = client.post(
        f"/api/v1/patron/actions/{uuid4()}/transitions",
        json=_transition_payload(),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}
