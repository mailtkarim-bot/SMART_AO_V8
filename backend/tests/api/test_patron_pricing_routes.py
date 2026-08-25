from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.patron_pricing import build_patron_pricing_router
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
        context_resolver=_Resolver(error=resolver_error),
        policy=SimpleNamespace(),
    )


def _client(*, service=None, transition_service=None, resolver_error=None) -> TestClient:
    app = FastAPI()
    app.include_router(
        build_patron_pricing_router(
            service=service or _PricingService(),
            transition_service=transition_service or _TransitionService(),
            security_runtime=_runtime(resolver_error=resolver_error),
        )
    )
    return TestClient(app, raise_server_exceptions=False)


def _result(*, replayed: bool = False, result_code: str) -> SimpleNamespace:
    return SimpleNamespace(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        result_code=result_code,
        aggregate_refs=[{"aggregate_id": str(uuid4()), "aggregate_revision": 2}],
        event_ids=[str(uuid4())],
        replayed=replayed,
    )


def _create_payload() -> dict[str, object]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "scenario_id": str(uuid4()),
        "source_snapshot_id": str(uuid4()),
        "scenario_key": "BASE-2026",
        "scenario_type": "BASE",
        "sales_adjustment_bps": 0,
        "cost_adjustment_bps": 0,
        "assumptions": {"source": "validated-snapshot"},
    }


def _transition_payload() -> dict[str, object]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "transition_id": str(uuid4()),
        "expected_version": 1,
        "reason_code": "PATRON_REVIEW",
    }


@dataclass
class _Scenario:
    scenario_id: object
    case_id: object
    scenario_key: str
    scenario_type: str
    version: int
    state: str
    assumptions: dict[str, object]
    sales_total_minor: int
    total_cost_minor: int
    gross_margin_minor: int
    gross_margin_rate_bps: int
    penalty_reserve_minor: int
    retention_reserve_minor: int
    guarantee_reserve_minor: int
    floor_margin_rate_bps: int
    target_margin_rate_bps: int
    break_even_sales_minor: int
    floor_sales_minor: int
    target_sales_minor: int
    source_snapshot_revision: int


class _PricingService:
    def __init__(self, *, execute_error=None, list_error=None):
        self.execute_error = execute_error
        self.list_error = list_error
        self.execute_calls = 0
        self.commands = []

    def list_for_case(self, **kwargs):
        if self.list_error is not None:
            raise self.list_error
        case_id = kwargs["case_id"]
        return [
            _Scenario(
                scenario_id=uuid4(),
                case_id=case_id,
                scenario_key="BASE-2026",
                scenario_type="BASE",
                version=1,
                state="DRAFT",
                assumptions={"source": "snapshot"},
                sales_total_minor=120_000,
                total_cost_minor=100_000,
                gross_margin_minor=20_000,
                gross_margin_rate_bps=1667,
                penalty_reserve_minor=0,
                retention_reserve_minor=0,
                guarantee_reserve_minor=0,
                floor_margin_rate_bps=0,
                target_margin_rate_bps=0,
                break_even_sales_minor=100_000,
                floor_sales_minor=100_000,
                target_sales_minor=100_000,
                source_snapshot_revision=4,
            )
        ]

    def execute(self, **kwargs):
        self.execute_calls += 1
        self.commands.append(kwargs["command"])
        if self.execute_error is not None:
            raise self.execute_error
        return _result(
            replayed=self.execute_calls > 1,
            result_code="PRICING_SCENARIO_CREATED",
        )


class _TransitionService:
    def __init__(self, *, error=None):
        self.error = error
        self.calls = 0

    def execute(self, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return _result(
            replayed=self.calls > 1,
            result_code="PRICING_SCENARIO_TRANSITIONED",
        )


def _headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


@pytest.mark.parametrize("authorization", [None, "Basic test-token", "Bearer"])
def test_pricing_routes_reject_missing_or_malformed_bearer(authorization):
    client = _client()
    headers = {} if authorization is None else {"Authorization": authorization}

    response = client.get(f"/api/v1/patron/cases/{uuid4()}/pricing-scenarios", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_pricing_routes_map_invalid_resolved_context_to_401():
    client = _client(resolver_error=UnauthenticatedError())

    response = client.post(
        f"/api/v1/patron/cases/{uuid4()}/pricing-scenarios",
        json=_create_payload(),
        headers=_headers(),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_list_scenarios_returns_financial_projection_for_patron():
    case_id = uuid4()
    response = _client().get(
        f"/api/v1/patron/cases/{case_id}/pricing-scenarios",
        headers=_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["case_id"] == str(case_id)
    assert body[0]["gross_margin_minor"] == 20_000
    assert body[0]["state"] == "DRAFT"


def test_list_scenarios_maps_permission_error_to_403():
    client = _client(service=_PricingService(list_error=PermissionError("PATRON_REQUIRED")))

    response = client.get(
        f"/api/v1/patron/cases/{uuid4()}/pricing-scenarios",
        headers=_headers(),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "FORBIDDEN"}


def test_create_scenario_forwards_cost_basis_inputs():
    service = _PricingService()
    client = _client(service=service)
    payload = _create_payload()
    payload.update(
        {
            "penalty_reserve_minor": 1000,
            "retention_reserve_minor": 500,
            "guarantee_reserve_minor": 250,
            "floor_margin_rate_bps": 1000,
            "target_margin_rate_bps": 2000,
        }
    )

    response = client.post(
        f"/api/v1/patron/cases/{uuid4()}/pricing-scenarios",
        json=payload,
        headers=_headers(),
    )

    assert response.status_code == 201
    command = service.commands[0]
    assert command.penalty_reserve_minor == 1000
    assert command.retention_reserve_minor == 500
    assert command.guarantee_reserve_minor == 250
    assert command.floor_margin_rate_bps == 1000
    assert command.target_margin_rate_bps == 2000


def test_create_scenario_returns_201_then_200_on_replay():
    service = _PricingService()
    client = _client(service=service)
    case_id = uuid4()
    payload = _create_payload()

    first = client.post(
        f"/api/v1/patron/cases/{case_id}/pricing-scenarios",
        json=payload,
        headers=_headers(),
    )
    replay = client.post(
        f"/api/v1/patron/cases/{case_id}/pricing-scenarios",
        json=payload,
        headers=_headers(),
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert first.json()["result_code"] == "PRICING_SCENARIO_CREATED"
    assert replay.json()["replayed"] is True
    assert service.execute_calls == 2


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("PATRON_REQUIRED"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("IDEMPOTENCY_KEY_REUSED"), 409, "IDEMPOTENCY_KEY_REUSED"),
        (CommandInProgressError("COMMAND_IN_PROGRESS"), 409, "COMMAND_IN_PROGRESS"),
        (CommandExecutionError("INVALID_ASSUMPTIONS"), 422, "INVALID_ASSUMPTIONS"),
    ],
)
def test_create_scenario_maps_service_errors(error, status_code, detail):
    client = _client(service=_PricingService(execute_error=error))

    response = client.post(
        f"/api/v1/patron/cases/{uuid4()}/pricing-scenarios",
        json=_create_payload(),
        headers=_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_select_scenario_returns_201_then_200_on_replay():
    transition_service = _TransitionService()
    client = _client(transition_service=transition_service)
    case_id = uuid4()
    scenario_id = uuid4()
    payload = _transition_payload()

    first = client.post(
        f"/api/v1/patron/cases/{case_id}/pricing-scenarios/{scenario_id}/selection",
        json=payload,
        headers=_headers(),
    )
    replay = client.post(
        f"/api/v1/patron/cases/{case_id}/pricing-scenarios/{scenario_id}/selection",
        json=payload,
        headers=_headers(),
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert first.json()["result_code"] == "PRICING_SCENARIO_TRANSITIONED"
    assert replay.json()["replayed"] is True


def test_archive_scenario_uses_archive_command_and_returns_receipt():
    transition_service = _TransitionService()
    client = _client(transition_service=transition_service)

    response = client.post(
        f"/api/v1/patron/cases/{uuid4()}/pricing-scenarios/{uuid4()}/archive",
        json=_transition_payload(),
        headers=_headers(),
    )

    assert response.status_code == 201
    assert response.json()["result_code"] == "PRICING_SCENARIO_TRANSITIONED"
    assert transition_service.calls == 1


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("PATRON_REQUIRED"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandInProgressError("running"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandExecutionError("VERSION_CONFLICT"), 409, "VERSION_CONFLICT"),
        (CommandExecutionError("SCENARIO_ALREADY_SELECTED"), 409, "SCENARIO_ALREADY_SELECTED"),
        (CommandExecutionError("SCENARIO_ALREADY_ARCHIVED"), 409, "SCENARIO_ALREADY_ARCHIVED"),
        (CommandExecutionError("INVALID_TRANSITION"), 422, "INVALID_TRANSITION"),
    ],
)
def test_select_scenario_maps_service_errors(error, status_code, detail):
    client = _client(transition_service=_TransitionService(error=error))

    response = client.post(
        f"/api/v1/patron/cases/{uuid4()}/pricing-scenarios/{uuid4()}/selection",
        json=_transition_payload(),
        headers=_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_pricing_payload_rejects_forbidden_extra_fields():
    response = _client().post(
        f"/api/v1/patron/cases/{uuid4()}/pricing-scenarios",
        json={**_create_payload(), "tenant_id": str(uuid4())},
        headers=_headers(),
    )

    assert response.status_code == 422
