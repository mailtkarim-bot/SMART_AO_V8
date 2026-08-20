from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.patron_pricing_import import (
    build_patron_pricing_import_router,
)
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
        return ActorContext(
            actor_id=uuid4(), identity_id=uuid4(), tenant_id=uuid4(), membership_id=uuid4(),
            actor_kind=ActorKind.PATRON_ADMIN, membership_state=MembershipState.ACTIVE,
            capabilities=frozenset(), assigned_case_ids=frozenset(), session_id=uuid4(),
            authenticated_at=NOW, mfa_verified_at=None, correlation_id=uuid4(),
        )


def _runtime(*, resolver_error=None):
    return ConsultationSecurityRuntime(
        context_resolver=_Resolver(error=resolver_error), policy=SimpleNamespace()
    )


def _client(*, service=None, commit_service=None, resolver_error=None):
    app = FastAPI()
    app.include_router(
        build_patron_pricing_import_router(
            service=service or _PreviewService(),
            commit_service=commit_service,
            security_runtime=_runtime(resolver_error=resolver_error),
        )
    )
    return TestClient(app, raise_server_exceptions=False)


@dataclass
class _Row:
    row_number: int
    code: str | None
    designation: str | None
    unit: str | None
    quantity_decimal: str | None
    unit_price_minor: int | None
    total_minor: int | None
    errors: list[str]


class _PreviewService:
    def __init__(self, *, error=None):
        self.error = error
        self.calls = []

    def preview(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            case_id=kwargs["case_id"], document_kind=kwargs["document_kind"],
            filename=kwargs["filename"], row_count=2, valid_row_count=1, error_count=1,
            total_minor=125000,
            rows=[
                _Row(1, "A-1", "Ouvrage", "U", "10", 12500, 125000, []),
                _Row(2, None, "Ligne invalide", None, None, None, None, ["CODE_REQUIRED"]),
            ],
        )


class _CommitService:
    def __init__(self, *, error=None):
        self.error = error

    def commit(self, **kwargs):
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            command_id=str(uuid4()), idempotency_key=str(uuid4()),
            result_code="PRICING_IMPORT_COMMITTED",
            aggregate_refs=[
                {"aggregate_type": "PricingImportBatch", "aggregate_id": str(uuid4()),
                 "aggregate_revision": 2}
            ],
            event_ids=[str(uuid4())], replayed=False,
        )


def _headers():
    return {"Authorization": "Bearer test-token"}


def _commit_payload():
    return {
        "command_id": str(uuid4()), "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()), "report_id": str(uuid4()),
        "expected_batch_revision": 1, "expected_report_revision": 2,
    }


@pytest.mark.parametrize("authorization", [None, "Basic test-token", "Bearer"])
def test_pricing_import_preview_rejects_missing_or_malformed_bearer(authorization):
    client = _client()
    headers = {} if authorization is None else {"Authorization": authorization}
    response = client.post(
        f"/api/v1/patron/cases/{uuid4()}/pricing-import/preview",
        files={"upload": ("pricing.xlsx", b"code;designation", "application/vnd.ms-excel")},
        headers=headers,
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_pricing_import_preview_maps_invalid_context_to_401():
    response = _client(resolver_error=UnauthenticatedError()).post(
        f"/api/v1/patron/cases/{uuid4()}/pricing-import/preview",
        files={"upload": ("pricing.xlsx", b"content", "application/octet-stream")},
        headers=_headers(),
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_pricing_import_preview_returns_rows_and_query_document_kind():
    service = _PreviewService()
    case_id = uuid4()
    response = _client(service=service).post(
        f"/api/v1/patron/cases/{case_id}/pricing-import/preview?document_kind=DPGF",
        files={"upload": ("dpgf.csv", b"A-1;Ouvrage", "text/csv")},
        headers=_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == str(case_id)
    assert body["document_kind"] == "DPGF"
    assert body["rows"][1]["errors"] == ["CODE_REQUIRED"]
    assert service.calls[0]["payload"] == b"A-1;Ouvrage"


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [(PermissionError("FORBIDDEN"), 403, "FORBIDDEN"),
     (ValueError("UNSUPPORTED_MEDIA_TYPE"), 422, "UNSUPPORTED_MEDIA_TYPE")],
)
def test_pricing_import_preview_maps_service_errors(error, status_code, detail):
    response = _client(service=_PreviewService(error=error)).post(
        f"/api/v1/patron/cases/{uuid4()}/pricing-import/preview",
        files={"upload": ("pricing.xlsx", b"content", "application/octet-stream")},
        headers=_headers(),
    )
    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_pricing_import_commit_returns_success_receipt():
    response = _client(commit_service=_CommitService()).post(
        f"/api/v1/patron/cases/{uuid4()}/pricing-import/{uuid4()}/commit",
        json=_commit_payload(), headers=_headers(),
    )
    assert response.status_code == 201
    assert response.json()["result_code"] == "PRICING_IMPORT_COMMITTED"
    assert response.json()["aggregate_refs"][0]["aggregate_type"] == "PricingImportBatch"


def test_pricing_import_commit_route_is_not_registered_without_service():
    response = _client().post(
        f"/api/v1/patron/cases/{uuid4()}/pricing-import/{uuid4()}/commit",
        json=_commit_payload(), headers=_headers(),
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [(PermissionError("FORBIDDEN"), 403, "FORBIDDEN"),
     (CommandExecutionError("IMPORT_NOT_FOUND_OR_FORBIDDEN"), 404,
      "IMPORT_NOT_FOUND_OR_FORBIDDEN"),
     (CommandExecutionError("FINANCIAL_REPORT_NOT_FOUND_OR_FORBIDDEN"), 404,
      "FINANCIAL_REPORT_NOT_FOUND_OR_FORBIDDEN"),
     (CommandExecutionError("VERSION_CONFLICT"), 409, "VERSION_CONFLICT"),
     (CommandExecutionError("IMPORT_ALREADY_COMMITTED"), 409, "IMPORT_ALREADY_COMMITTED"),
     (CommandExecutionError("INVALID_ROW"), 422, "INVALID_ROW")],
)
def test_pricing_import_commit_maps_service_errors(error, status_code, detail):
    response = _client(commit_service=_CommitService(error=error)).post(
        f"/api/v1/patron/cases/{uuid4()}/pricing-import/{uuid4()}/commit",
        json=_commit_payload(), headers=_headers(),
    )
    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_pricing_import_preview_rejects_unknown_document_kind():
    response = _client().post(
        f"/api/v1/patron/cases/{uuid4()}/pricing-import/preview?document_kind=PDF",
        files={"upload": ("pricing.pdf", b"content", "application/pdf")},
        headers=_headers(),
    )
    assert response.status_code == 422
