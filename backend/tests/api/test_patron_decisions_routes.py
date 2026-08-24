from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.patron_decisions import build_patron_decision_router
from app.platform.events.dispatcher import CommandExecutionError
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


def _client(
    *, service=None, risk_service=None, risk_requirement_service=None, finalization_service=None,
    risk_requirement_read_service=None, resolver_error=None
):
    app = FastAPI()
    app.include_router(
        build_patron_decision_router(
            service=service or _DecisionService(),
            risk_service=risk_service,
            risk_requirement_service=risk_requirement_service,
            finalization_service=finalization_service,
            risk_requirement_read_service=risk_requirement_read_service,
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


def _risk_payload():
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "risk_id": str(uuid4()),
        "dce_version_id": str(uuid4()),
        "source_fragment_id": str(uuid4()),
        "category": "CCAP",
        "risk_code": "CCAP-DELAI-001",
        "title": "Délai contractuel critique",
        "statement": "Le délai impose une mobilisation anticipée.",
        "severity": "HIGH",
        "likelihood": "LIKELY",
        "source_excerpt": "Le titulaire respecte le délai contractuel.",
        "source_locator": {"page": 12, "section": "CCAP 4.2"},
        "start_byte_offset": 100,
        "end_byte_offset": 150,
    }


class _RiskService:
    def __init__(self, *, error=None):
        self.error = error
        self.calls = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        result = SimpleNamespace(
            command_id=str(kwargs["command"].command_id),
            idempotency_key=str(kwargs["command"].idempotency_key),
            result_code="DECISION_RISK_REGISTERED",
            aggregate_refs=[
                {
                    "aggregate_id": str(kwargs["command"].risk_id),
                    "aggregate_revision": 1,
                }
            ],
            event_ids=[str(uuid4())],
            replayed=False,
        )
        return result


class _RiskRequirementService:
    def __init__(self, *, error=None):
        self.error = error
        self.calls = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        result = SimpleNamespace(
            command_id=str(kwargs["command"].command_id),
            idempotency_key=str(kwargs["command"].idempotency_key),
            result_code="DECISION_RISK_REQUIREMENT_LINKED",
            aggregate_refs=[
                {
                    "aggregate_id": str(kwargs["command"].link_id),
                    "aggregate_revision": 1,
                }
            ],
            event_ids=[str(uuid4())],
            replayed=False,
        )
        return result


class _ReadService:
    def __init__(self, *, error=None):
        self.error = error

    def list_links(self, **kwargs):
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            items=(
                SimpleNamespace(
                    link_id=uuid4(),
                    case_id=kwargs["case_id"],
                    risk_id=uuid4(),
                    requirement_id=uuid4(),
                    dce_version_id=uuid4(),
                    relationship="IMPACTS",
                    rationale="Revue patronale requise.",
                    source_refs=("decision-risk:1", "dce-requirement:2"),
                    created_at=datetime.now(tz=UTC),
                    action_id=uuid4(),
                    action_state="OPEN",
                    action_severity="BLOCKING",
                    action_revision=1,
                ),
            ),
            next_cursor="next-page",
        )

    def reconcile_pricing(self, **kwargs):
        if self.error is not None:
            raise self.error
        return (
            SimpleNamespace(
                link_id=kwargs["link_id"],
                batch_id=uuid4(),
                document_kind="DPGF",
                batch_state="COMMITTED",
                row_number=12,
                code="BET-001",
                designation="Béton de structure",
                unit="m3",
                match_basis="CODE_OR_DESIGNATION",
                verification_status="COMMITTED_NORMALIZED_IMPORT",
            ),
        )


class _FinalizeService:
    def __init__(self, *, error=None):
        self.error = error
        self.calls = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        result = SimpleNamespace(
            command_id=str(kwargs["command"].command_id),
            idempotency_key=str(kwargs["command"].idempotency_key),
            result_code="DECISION_FINALIZED",
            aggregate_refs=[
                {
                    "aggregate_id": str(kwargs["command"].decision_id),
                    "aggregate_revision": 4,
                }
            ],
            event_ids=[str(uuid4())],
            replayed=False,
        )
        return result


class _DecisionService:
    def __init__(self, *, error=None):
        self.error = error

    def read(self, **kwargs):
        if self.error is not None:
            raise self.error
        return _dossier(kwargs["case_id"])


def _link_payload():
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "link_id": str(uuid4()),
        "requirement_id": str(uuid4()),
        "dce_version_id": str(uuid4()),
        "relationship": "IMPACTS",
        "rationale": "L’exigence confirmée doit être prise en compte pour traiter le risque.",
    }


def _finalize_payload():
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_revision": 3,
        "displayed_fingerprint": "a" * 64,
        "outcome": "GO",
        "justification": "Le patron finalise après revue humaine des sources confirmées.",
    }


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


def test_register_risk_returns_closed_patron_receipt_and_forwards_case_from_path():
    risk_service = _RiskService()
    case_id = uuid4()
    payload = _risk_payload()

    response = _client(risk_service=risk_service).post(
        f"/api/v1/patron/cases/{case_id}/risks",
        json=payload,
        headers=_headers(),
    )

    assert response.status_code == 201
    assert response.json()["result_code"] == "DECISION_RISK_REGISTERED"
    assert risk_service.calls[0]["command"].case_id == case_id
    assert "source_excerpt" not in response.json()
    assert "statement" not in response.json()


def test_register_risk_maps_permission_error_to_403():
    response = _client(
        risk_service=_RiskService(error=PermissionError("PATRON_REQUIRED"))
    ).post(
        f"/api/v1/patron/cases/{uuid4()}/risks",
        json=_risk_payload(),
        headers=_headers(),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "FORBIDDEN"}


def test_register_risk_rejects_forbidden_extra_fields():
    response = _client(risk_service=_RiskService()).post(
        f"/api/v1/patron/cases/{uuid4()}/risks",
        json={**_risk_payload(), "tenant_id": str(uuid4())},
        headers=_headers(),
    )

    assert response.status_code == 422


def test_link_risk_requirement_returns_closed_receipt_and_forwards_path_ids():
    link_service = _RiskRequirementService()
    case_id = uuid4()
    risk_id = uuid4()

    response = _client(risk_requirement_service=link_service).post(
        f"/api/v1/patron/cases/{case_id}/risks/{risk_id}/requirements",
        json=_link_payload(),
        headers=_headers(),
    )

    assert response.status_code == 201
    assert response.json()["result_code"] == "DECISION_RISK_REQUIREMENT_LINKED"
    command = link_service.calls[0]["command"]
    assert command.case_id == case_id
    assert command.risk_id == risk_id
    assert "rationale" not in response.json()


def test_link_risk_requirement_maps_duplicate_to_409():
    response = _client(
        risk_requirement_service=_RiskRequirementService(
            error=CommandExecutionError("RISK_REQUIREMENT_LINK_ALREADY_EXISTS")
        )
    ).post(
        f"/api/v1/patron/cases/{uuid4()}/risks/{uuid4()}/requirements",
        json=_link_payload(),
        headers=_headers(),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "RISK_REQUIREMENT_LINK_ALREADY_EXISTS"}


def test_link_risk_requirement_rejects_forbidden_extra_fields():
    response = _client(risk_requirement_service=_RiskRequirementService()).post(
        f"/api/v1/patron/cases/{uuid4()}/risks/{uuid4()}/requirements",
        json={**_link_payload(), "tenant_id": str(uuid4())},
        headers=_headers(),
    )

    assert response.status_code == 422


def test_list_risk_requirement_links_returns_paged_patron_projection():
    case_id = uuid4()
    response = _client(risk_requirement_read_service=_ReadService()).get(
        f"/api/v1/patron/cases/{case_id}/risk-requirement-links?limit=10",
        headers=_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["next_cursor"] == "next-page"
    assert body["items"][0]["case_id"] == str(case_id)
    assert body["items"][0]["action_state"] == "OPEN"


def test_reconcile_pricing_returns_no_monetary_columns():
    case_id = uuid4()
    link_id = uuid4()
    response = _client(risk_requirement_read_service=_ReadService()).get(
        f"/api/v1/patron/cases/{case_id}/risk-requirement-links/{link_id}/pricing-reconciliation",
        params={"search": "béton", "limit": 10},
        headers=_headers(),
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["document_kind"] == "DPGF"
    assert "unit_price_minor" not in item
    assert "total_minor" not in item


def test_collaborator_read_service_error_maps_to_forbidden():
    response = _client(
        risk_requirement_read_service=_ReadService(error=PermissionError("PATRON_REQUIRED"))
    ).get(
        f"/api/v1/patron/cases/{uuid4()}/risk-requirement-links",
        headers=_headers(),
    )

    assert response.status_code == 403


def test_finalize_conditional_go_returns_condition_count():
    payload = _finalize_payload()
    payload["outcome"] = "CONDITIONAL_GO"
    payload["conditions"] = [
        {
            "condition_id": str(uuid4()),
            "label": "Obtenir la validation documentaire",
            "owner_actor_id": str(uuid4()),
            "due_date_absence_reason": "Date fixée dans le planning patronal.",
            "failure_consequence": "Réexaminer la décision.",
        }
    ]
    response = _client(finalization_service=_FinalizeService()).post(
        f"/api/v1/patron/cases/{uuid4()}/decisions/{uuid4()}/go-no-go",
        json=payload,
        headers=_headers(),
    )

    assert response.status_code == 200
    assert response.json()["condition_count"] == 1


def test_finalize_go_no_go_returns_closed_receipt_and_forwards_path_ids():
    finalization_service = _FinalizeService()
    case_id = uuid4()
    decision_id = uuid4()

    response = _client(finalization_service=finalization_service).post(
        f"/api/v1/patron/cases/{case_id}/decisions/{decision_id}/go-no-go",
        json=_finalize_payload(),
        headers=_headers(),
    )

    assert response.status_code == 200
    assert response.json()["result_code"] == "DECISION_FINALIZED"
    command = finalization_service.calls[0]["command"]
    assert command.case_id == case_id
    assert command.decision_id == decision_id
    assert "justification" not in response.json()


def test_finalize_go_no_go_maps_stale_revision_to_409():
    response = _client(
        finalization_service=_FinalizeService(
            error=CommandExecutionError("STALE_DECISION_REVISION")
        )
    ).post(
        f"/api/v1/patron/cases/{uuid4()}/decisions/{uuid4()}/go-no-go",
        json=_finalize_payload(),
        headers=_headers(),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "STALE_DECISION_REVISION"}


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
