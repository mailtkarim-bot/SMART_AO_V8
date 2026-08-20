from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.interfaces.http.routes.assignment_interactions import (
    build_assignment_interaction_router,
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
        build_assignment_interaction_router(
            service=service or _InteractionService(),
            security_runtime=_runtime(resolver_error=resolver_error),
        )
    )
    return TestClient(app, raise_server_exceptions=False)


def _result(*, code, replayed=False):
    return SimpleNamespace(
        command_id=uuid4(), idempotency_key=uuid4(), result_code=code,
        aggregate_refs=[{"aggregate_type": "CaseAssignment", "aggregate_id": str(uuid4()),
                         "aggregate_revision": 2}],
        event_ids=[str(uuid4())], replayed=replayed,
    )


def _base():
    return {
        "command_id": str(uuid4()), "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()), "expected_revision": 1,
    }


def _ack_payload():
    return {**_base(), "note": "Affectation reçue."}


def _clarification_payload():
    return {
        **_base(), "clarification_kind": "DEADLINE", "subject": "Échéance",
        "question": "Quelle est la date de remise attendue ?", "requested_scope": "Planning",
        "priority": "HIGH",
    }


def _unavailability_payload():
    return {
        **_base(), "reason_kind": "CAPACITY_CONFLICT", "reason": "Conflit de capacité.",
        "unavailable_from": "2026-08-20T09:00:00Z",
        "unavailable_until": "2026-08-21T18:00:00Z",
        "known_deadline_impact": True, "impact_note": "Replanification nécessaire.",
    }


class _InteractionService:
    def __init__(self, *, error=None):
        self.error = error
        self.calls = []

    def _execute(self, name, **kwargs):
        self.calls.append((name, kwargs))
        if self.error is not None:
            raise self.error
        code = {
            "acknowledge": "ASSIGNMENT_ACKNOWLEDGED",
            "clarify": "ASSIGNMENT_CLARIFICATION_REQUESTED",
            "report_unavailability": "ASSIGNMENT_UNAVAILABILITY_REPORTED",
        }[name]
        return _result(code=code, replayed=len(self.calls) > 1)

    def acknowledge(self, **kwargs):
        return self._execute("acknowledge", **kwargs)

    def clarify(self, **kwargs):
        return self._execute("clarify", **kwargs)

    def report_unavailability(self, **kwargs):
        return self._execute("report_unavailability", **kwargs)


def _headers():
    return {"Authorization": "Bearer test-token"}


@pytest.mark.parametrize("authorization", [None, "Basic test-token", "Bearer"])
def test_assignment_interaction_routes_reject_missing_or_malformed_bearer(authorization):
    client = _client()
    headers = {} if authorization is None else {"Authorization": authorization}
    response = client.post(
        f"/api/v1/assignments/{uuid4()}/acknowledgement",
        json=_ack_payload(), headers=headers,
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_assignment_interaction_routes_map_invalid_context_to_401():
    response = _client(resolver_error=UnauthenticatedError()).post(
        f"/api/v1/assignments/{uuid4()}/clarification-requests",
        json=_clarification_payload(), headers=_headers(),
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_assignment_interaction_commands_return_receipts_and_forward_assignment_id():
    service = _InteractionService()
    client = _client(service=service)
    assignment_id = uuid4()
    paths = [
        (f"/api/v1/assignments/{assignment_id}/acknowledgement", _ack_payload(),
         "ASSIGNMENT_ACKNOWLEDGED"),
        (f"/api/v1/assignments/{assignment_id}/clarification-requests", _clarification_payload(),
         "ASSIGNMENT_CLARIFICATION_REQUESTED"),
        (f"/api/v1/assignments/{assignment_id}/unavailability-reports", _unavailability_payload(),
         "ASSIGNMENT_UNAVAILABILITY_REPORTED"),
    ]
    for index, (path, payload, code) in enumerate(paths):
        response = client.post(path, json=payload, headers=_headers())
        assert response.status_code == (201 if index == 0 else 200)
        assert response.json()["result_code"] == code
    assert all(call[1]["command"].assignment_id == assignment_id for call in service.calls)


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [(PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
     (PermissionError("FORBIDDEN"), 403, "FORBIDDEN"),
     (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_KEY_REUSED"),
     (CommandInProgressError("running"), 409, "COMMAND_IN_PROGRESS"),
     (CommandExecutionError("VERSION_CONFLICT"), 422, "COMMAND_REJECTED")],
)
def test_assignment_interaction_maps_service_errors(error, status_code, detail):
    response = _client(service=_InteractionService(error=error)).post(
        f"/api/v1/assignments/{uuid4()}/unavailability-reports",
        json=_unavailability_payload(), headers=_headers(),
    )
    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_assignment_interaction_payload_rejects_financial_fields():
    response = _client().post(
        f"/api/v1/assignments/{uuid4()}/acknowledgement",
        json={**_ack_payload(), "gross_margin_minor": 100}, headers=_headers(),
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("path", "payload"),
    [("acknowledgement", {**_base(), "expected_revision": -1}),
     ("clarification-requests", {**_base(), "clarification_kind": "INVALID",
                                  "subject": "x", "question": "x"})],
)
def test_assignment_interaction_payload_rejects_invalid_values(path, payload):
    response = _client().post(
        f"/api/v1/assignments/{uuid4()}/{path}", json=payload, headers=_headers()
    )
    assert response.status_code == 422
