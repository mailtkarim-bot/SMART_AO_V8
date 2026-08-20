from dataclasses import dataclass
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.interfaces.http.routes.collaborator_capabilities import (
    build_collaborator_capability_router,
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


@dataclass
class _Resolver:
    error: Exception | None = None

    def resolve(self, *, access_token: str) -> ActorContext:
        assert access_token == "test-token"
        if self.error is not None:
            raise self.error
        return _actor()


def _actor() -> ActorContext:
    from datetime import UTC, datetime

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
        authenticated_at=datetime.now(tz=UTC),
        mfa_verified_at=None,
        correlation_id=uuid4(),
    )


def _runtime(*, resolver_error: Exception | None = None) -> ConsultationSecurityRuntime:
    return ConsultationSecurityRuntime(
        context_resolver=_Resolver(error=resolver_error),
        policy=SimpleNamespace(),
    )


def _client(*, service=None, resolver_error=None) -> TestClient:
    app = FastAPI()
    app.include_router(
        build_collaborator_capability_router(
            service=service or _CapabilityService(),
            security_runtime=_runtime(resolver_error=resolver_error),
        )
    )
    return TestClient(app, raise_server_exceptions=False)


def _result(*, replayed: bool = False, result_code: str) -> SimpleNamespace:
    return SimpleNamespace(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        result_code=result_code,
        aggregate_refs=[{"aggregate_id": str(uuid4()), "aggregate_revision": 1}],
        event_ids=[str(uuid4())],
        replayed=replayed,
    )


def _proposal_payload() -> dict[str, object]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "assignment_id": str(uuid4()),
        "capability_id": str(uuid4()),
        "capability_version_id": str(uuid4()),
        "requirement_id": str(uuid4()),
        "task_id": str(uuid4()),
        "justification": "Référence travaux similaire validée.",
        "source_locator": "qualification:reference:42",
    }


def _gap_payload() -> dict[str, object]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "assignment_id": str(uuid4()),
        "capability_id": str(uuid4()),
        "requirement_id": str(uuid4()),
        "task_id": str(uuid4()),
        "gap_kind": "MISSING",
        "severity": "BLOCKING",
        "reason": "La qualification obligatoire n’est pas disponible.",
        "source_locator": "requirement:qualification:7",
        "recommended_action": "Demander une preuve de qualification valide.",
    }


class _CapabilityService:
    def __init__(self, *, propose_error=None, gap_error=None, read_error=None):
        self.propose_error = propose_error
        self.gap_error = gap_error
        self.read_error = read_error
        self.propose_calls = 0
        self.gap_calls = 0

    def propose_capability(self, **kwargs):
        self.propose_calls += 1
        if self.propose_error is not None:
            raise self.propose_error
        return _result(
            replayed=self.propose_calls > 1,
            result_code="CAPABILITY_PROPOSAL_CREATED",
        )

    def report_gap(self, **kwargs):
        self.gap_calls += 1
        if self.gap_error is not None:
            raise self.gap_error
        return _result(
            replayed=self.gap_calls > 1,
            result_code="CAPABILITY_GAP_REPORTED",
        )

    def read_assessments(self, **kwargs):
        if self.read_error is not None:
            raise self.read_error
        case_id = kwargs["case_id"]
        assignment_id = kwargs["assignment_id"]
        proposal = SimpleNamespace(
            proposal_id=uuid4(),
            case_id=case_id,
            assignment_id=assignment_id,
            capability_id=uuid4(),
            capability_version_id=uuid4(),
            requirement_id=uuid4(),
            task_id=uuid4(),
            state="PROPOSED",
            validity_state="CURRENT",
            justification="Référence pertinente.",
            source_locator="reference:42",
        )
        gap = SimpleNamespace(
            gap_id=uuid4(),
            case_id=case_id,
            assignment_id=assignment_id,
            capability_id=None,
            requirement_id=uuid4(),
            task_id=None,
            gap_kind="MISSING",
            severity="BLOCKING",
            reason="Preuve absente.",
            source_locator="requirement:7",
            recommended_action="Collecter la preuve.",
        )
        return SimpleNamespace(proposals=[proposal], gaps=[gap])


def _headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


@pytest.mark.parametrize("authorization", [None, "Basic test-token", "Bearer"])
def test_collaborator_capability_routes_reject_missing_or_malformed_bearer(authorization):
    client = _client()
    headers = {} if authorization is None else {"Authorization": authorization}

    response = client.post(
        f"/api/v1/collaborator/cases/{uuid4()}/capability-proposals",
        json=_proposal_payload(),
        headers=headers,
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_collaborator_capability_routes_map_invalid_context_to_401():
    client = _client(resolver_error=UnauthenticatedError())

    response = client.get(
        f"/api/v1/collaborator/cases/{uuid4()}/capability-assessments",
        params={"assignment_id": str(uuid4())},
        headers=_headers(),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_propose_capability_returns_201_then_200_on_replay():
    service = _CapabilityService()
    client = _client(service=service)
    case_id = uuid4()
    payload = _proposal_payload()

    first = client.post(
        f"/api/v1/collaborator/cases/{case_id}/capability-proposals",
        json=payload,
        headers=_headers(),
    )
    replay = client.post(
        f"/api/v1/collaborator/cases/{case_id}/capability-proposals",
        json=payload,
        headers=_headers(),
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert first.json()["result_code"] == "CAPABILITY_PROPOSAL_CREATED"
    assert replay.json()["replayed"] is True


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("ASSIGNMENT_REQUIRED"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandInProgressError("running"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandExecutionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (CommandExecutionError("SCOPE_DENIED"), 403, "FORBIDDEN"),
        (CommandExecutionError("ASSIGNMENT_REQUIRED"), 403, "FORBIDDEN"),
        (
            CommandExecutionError("CAPABILITY_PROPOSAL_ALREADY_EXISTS"),
            409,
            "CAPABILITY_PROPOSAL_ALREADY_EXISTS",
        ),
        (CommandExecutionError("INVALID_CAPABILITY"), 422, "COMMAND_REJECTED"),
    ],
)
def test_propose_capability_maps_service_errors(error, status_code, detail):
    client = _client(service=_CapabilityService(propose_error=error))

    response = client.post(
        f"/api/v1/collaborator/cases/{uuid4()}/capability-proposals",
        json=_proposal_payload(),
        headers=_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_report_gap_returns_201_then_200_on_replay():
    service = _CapabilityService()
    client = _client(service=service)
    case_id = uuid4()
    payload = _gap_payload()

    first = client.post(
        f"/api/v1/collaborator/cases/{case_id}/capability-gaps",
        json=payload,
        headers=_headers(),
    )
    replay = client.post(
        f"/api/v1/collaborator/cases/{case_id}/capability-gaps",
        json=payload,
        headers=_headers(),
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert first.json()["result_code"] == "CAPABILITY_GAP_REPORTED"
    assert replay.json()["replayed"] is True


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("PATRON_REQUIRED"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandInProgressError("running"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandExecutionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (CommandExecutionError("SCOPE_DENIED"), 403, "FORBIDDEN"),
        (CommandExecutionError("ASSIGNMENT_REQUIRED"), 403, "FORBIDDEN"),
        (
            CommandExecutionError("CAPABILITY_GAP_ALREADY_REPORTED"),
            409,
            "CAPABILITY_GAP_ALREADY_REPORTED",
        ),
        (CommandExecutionError("INVALID_GAP"), 422, "COMMAND_REJECTED"),
    ],
)
def test_report_gap_maps_service_errors(error, status_code, detail):
    client = _client(service=_CapabilityService(gap_error=error))

    response = client.post(
        f"/api/v1/collaborator/cases/{uuid4()}/capability-gaps",
        json=_gap_payload(),
        headers=_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_read_assessments_returns_proposals_and_gaps_without_financial_fields():
    case_id = uuid4()
    response = _client().get(
        f"/api/v1/collaborator/cases/{case_id}/capability-assessments",
        params={"assignment_id": str(uuid4())},
        headers=_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["proposals"][0]["state"] == "PROPOSED"
    assert body["gaps"][0]["severity"] == "BLOCKING"
    assert "sales_total_minor" not in body
    assert "gross_margin_minor" not in body
    assert "total_cost_minor" not in body


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("ASSIGNMENT_REQUIRED"), 403, "FORBIDDEN"),
        (CommandExecutionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (CommandExecutionError("SCOPE_DENIED"), 403, "FORBIDDEN"),
    ],
)
def test_read_assessments_maps_service_errors(error, status_code, detail):
    client = _client(service=_CapabilityService(read_error=error))

    response = client.get(
        f"/api/v1/collaborator/cases/{uuid4()}/capability-assessments",
        params={"assignment_id": str(uuid4())},
        headers=_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_collaborator_payload_rejects_financial_fields():
    response = _client().post(
        f"/api/v1/collaborator/cases/{uuid4()}/capability-gaps",
        json={**_gap_payload(), "gross_margin_minor": 100},
        headers=_headers(),
    )

    assert response.status_code == 422
