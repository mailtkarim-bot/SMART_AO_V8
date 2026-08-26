from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.patron_dce_contract_risks import (
    build_patron_dce_contract_risk_router,
)
from app.platform.security.context import ActorContext, ActorKind, MembershipState
from fastapi import FastAPI
from fastapi.testclient import TestClient

NOW = datetime(2026, 8, 26, 15, 0, tzinfo=UTC)


@dataclass
class _Resolver:
    def resolve(self, *, access_token: str) -> ActorContext:
        assert access_token == "test-token"
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


class _Service:
    def list_for_case(self, **kwargs):
        return (
            SimpleNamespace(
                observation_id=uuid4(),
                dce_version_id=uuid4(),
                document_family="CCAP",
                requirement_kind="CCAP_PENALTIES",
                rule_id="CCAP_DELAY_PENALTIES_V1",
                rule_version="2",
                directive="REQUIRED_SIGNAL",
                fragment_id=uuid4(),
                source_locator_label="CCAP · page 7",
                start_byte_offset=12,
                end_byte_offset=74,
                verification_status="REVIEW_REQUIRED",
            ),
        )


def _client(*, service=None):
    app = FastAPI()
    app.include_router(
        build_patron_dce_contract_risk_router(
            service=service or _Service(),
            security_runtime=ConsultationSecurityRuntime(
                context_resolver=_Resolver(),
                policy=SimpleNamespace(),
            ),
        )
    )
    return TestClient(app)


def test_contract_risk_endpoint_returns_closed_non_financial_projection():
    case_id = uuid4()
    response = _client().get(
        f"/api/v1/patron/cases/{case_id}/dce-contract-risk-signals?limit=20",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == str(case_id)
    item = body["items"][0]
    assert item["requirement_kind"] == "CCAP_PENALTIES"
    assert item["verification_status"] == "REVIEW_REQUIRED"
    assert item["source_locator_label"] == "CCAP · page 7"
    assert "excerpt" not in item
    assert "unit_price_minor" not in item
    assert "total_minor" not in item


def test_contract_risk_endpoint_maps_service_permission_to_403():
    class _ForbiddenService:
        def list_for_case(self, **kwargs):
            raise PermissionError("PATRON_REQUIRED")

    response = _client(service=_ForbiddenService()).get(
        f"/api/v1/patron/cases/{uuid4()}/dce-contract-risk-signals",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "FORBIDDEN"}
