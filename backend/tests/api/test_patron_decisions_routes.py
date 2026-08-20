from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.patron_decisions import build_patron_decision_router
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
        build_patron_decision_router(
            service=service or _DecisionService(),
            security_runtime=_runtime(resolver_error=resolver_error),
        )
    )
    return TestClient(app, raise_server_exceptions=False)


@dataclass(frozen=True)
class _Dossier:
    decision_id: object
    case_id: object
    decision_type: str
    lifecycle: str
    outcome: str
    validity: str
    context_status: str
    final_justification: str | None
    known: tuple[object, ...]
    unknowns: tuple[object, ...]
    risks: tuple[object, ...]
    conditions: tuple[dict[str, object], ...]
    sources: tuple[dict[str, object], ...]


def _dossier(case_id):
    return _Dossier(
        decision_id=uuid4(),
        case_id=case_id,
        decision_type="AWARD",
        lifecycle="FINAL",
        outcome="GO",
        validity="CURRENT",
        context_status="FROZEN",
        final_justification="Les pièces validées soutiennent la décision.",
        known=("Préparation complète",),
        unknowns=("Planning fournisseur à confirmer",),
        risks=("Risque de délai",),
        conditions=(
            {
                "condition_id": uuid4(),
                "label": "Signer le marché",
                "status": "OPEN",
                "due_at": None,
                "failure_consequence": "Décision suspendue",
            },
        ),
        sources=(
            {
                "aggregate_type": "PREPARATION_SNAPSHOT",
                "aggregate_id": uuid4(),
                "aggregate_revision": 4,
                "role": "PRIMARY",
            },
        ),
    )


class _DecisionService:
    def __init__(self, *, error=None):
        self.error = error

    def read(self, **kwargs):
        if self.error is not None:
            raise self.error
        return _dossier(kwargs["case_id"])


def _headers():
    return {"Authorization": "Bearer test-token"}


@pytest.mark.parametrize("authorization", [None, "Basic test-token", "Bearer"])
def test_decision_route_rejects_missing_or_malformed_bearer(authorization):
    client = _client()
    headers = {} if authorization is None else {"Authorization": authorization}

    response = client.get(f"/api/v1/patron/cases/{uuid4()}/decision-dossier", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_decision_route_maps_invalid_context_to_401():
    response = _client(resolver_error=UnauthenticatedError()).get(
        f"/api/v1/patron/cases/{uuid4()}/decision-dossier",
        headers=_headers(),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_read_decision_dossier_returns_frozen_projection():
    case_id = uuid4()
    response = _client().get(
        f"/api/v1/patron/cases/{case_id}/decision-dossier",
        headers=_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == str(case_id)
    assert body["context_status"] == "FROZEN"
    assert body["conditions"][0]["status"] == "OPEN"
    assert body["sources"][0]["aggregate_type"] == "PREPARATION_SNAPSHOT"
    assert "gross_margin_minor" not in body
    assert "total_cost_minor" not in body


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (PermissionError("PATRON_REQUIRED"), 403, "FORBIDDEN"),
        (PermissionError("DECISION_CONTEXT_NOT_FOUND"), 403, "FORBIDDEN"),
    ],
)
def test_read_decision_dossier_maps_service_errors(error, status_code, detail):
    response = _client(service=_DecisionService(error=error)).get(
        f"/api/v1/patron/cases/{uuid4()}/decision-dossier",
        headers=_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}
