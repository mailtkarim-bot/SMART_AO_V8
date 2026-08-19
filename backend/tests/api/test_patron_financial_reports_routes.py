from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.patron_financial_reports import (
    build_patron_financial_report_router,
)
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


def _runtime(*, resolver_error=None):
    return ConsultationSecurityRuntime(
        context_resolver=_Resolver(error=resolver_error), policy=SimpleNamespace()
    )


def _client(*, service=None, line_service=None, draft_service=None, publication_service=None,
            resolver_error=None):
    app = FastAPI()
    app.include_router(
        build_patron_financial_report_router(
            service=service or _ReportService(),
            line_service=line_service or _FinancialCommandService(),
            draft_creation_service=draft_service or _FinancialCommandService(),
            publication_service=publication_service or _FinancialCommandService(),
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
            {"aggregate_type": "FinancialReportSnapshot", "aggregate_id": str(uuid4()),
             "aggregate_revision": 2}
        ],
        event_ids=[str(uuid4())],
        replayed=replayed,
    )


def _draft_payload():
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "currency_code": "EUR",
        "ruleset_version": 1,
    }


def _line_payload():
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_revision": 1,
        "category": "SALES",
        "label": "Chiffre d’affaires prévisionnel",
        "quantity_decimal": "10.5",
        "unit": "DAY",
        "amount_minor": 125000,
    }


def _publish_payload():
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_revision": 2,
    }


@dataclass
class _Line:
    line_id: object
    category: str
    label: str
    quantity_decimal: str
    unit: str
    amount_minor: int
    currency_code: str


class _ReportService:
    def __init__(self, *, error=None):
        self.error = error

    def _projection(self, case_id, report_id):
        line = _Line(uuid4(), "SALES", "Ventes", "10", "DAY", 125000, "EUR")
        return SimpleNamespace(
            report_id=report_id,
            case_id=case_id,
            aggregate_revision=2,
            currency_code="EUR",
            calculated_at=NOW,
            ruleset_version=1,
            summary={
                "sales_total_minor": 125000,
                "direct_cost_total_minor": 50000,
                "overhead_total_minor": 10000,
                "subcontracting_total_minor": 0,
                "contingency_total_minor": 5000,
                "gross_margin_minor": 60000,
                "gross_margin_rate_bps": 4800,
                "forecast_cashflow_minor": 60000,
            },
            lines=[line],
        )

    def get_draft(self, **kwargs):
        if self.error is not None:
            raise self.error
        return self._projection(kwargs["case_id"], kwargs["report_id"])

    def get(self, **kwargs):
        if self.error is not None:
            raise self.error
        return self._projection(kwargs["case_id"], kwargs["report_id"])


class _FinancialCommandService:
    def __init__(self, *, error=None):
        self.error = error
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return _result(code="FINANCIAL_REPORT_DRAFT_CREATED", replayed=self.calls > 1)

    def add_line(self, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return _result(code="FINANCIAL_REPORT_LINE_ADDED", replayed=self.calls > 1)

    def publish(self, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return _result(code="FINANCIAL_REPORT_PUBLISHED", replayed=self.calls > 1)


def _headers():
    return {"Authorization": "Bearer test-token"}


@pytest.mark.parametrize("authorization", [None, "Basic test-token", "Bearer"])
def test_financial_report_routes_reject_missing_or_malformed_bearer(authorization):
    client = _client()
    headers = {} if authorization is None else {"Authorization": authorization}

    response = client.get(
        f"/api/v1/patron/cases/{uuid4()}/financial-reports/{uuid4()}/draft",
        headers=headers,
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_financial_report_routes_map_invalid_context_to_401():
    response = _client(resolver_error=UnauthenticatedError()).post(
        f"/api/v1/patron/cases/{uuid4()}/financial-reports/drafts",
        json=_draft_payload(),
        headers=_headers(),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_financial_command_routes_return_201_then_200_replay():
    draft_service = _FinancialCommandService()
    line_service = _FinancialCommandService()
    publication_service = _FinancialCommandService()
    client = _client(
        draft_service=draft_service,
        line_service=line_service,
        publication_service=publication_service,
    )
    case_id = uuid4()
    report_id = uuid4()
    first = client.post(
        f"/api/v1/patron/cases/{case_id}/financial-reports/drafts",
        json=_draft_payload(),
        headers=_headers(),
    )
    replay = client.post(
        f"/api/v1/patron/cases/{case_id}/financial-reports/{report_id}/lines",
        json=_line_payload(),
        headers=_headers(),
    )
    published = client.post(
        f"/api/v1/patron/cases/{case_id}/financial-reports/{report_id}/publications",
        json=_publish_payload(),
        headers=_headers(),
    )

    assert first.status_code == 201
    assert replay.status_code == 201
    assert published.status_code == 201
    assert first.json()["result_code"] == "FINANCIAL_REPORT_DRAFT_CREATED"
    assert replay.json()["result_code"] == "FINANCIAL_REPORT_LINE_ADDED"
    assert published.json()["result_code"] == "FINANCIAL_REPORT_PUBLISHED"


def test_financial_command_route_replays_when_same_service_is_reused():
    service = _FinancialCommandService()
    client = _client(draft_service=service)
    path = f"/api/v1/patron/cases/{uuid4()}/financial-reports/drafts"
    first = client.post(path, json=_draft_payload(), headers=_headers())
    replay = client.post(path, json=_draft_payload(), headers=_headers())

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (PermissionError("FINANCIAL_REPORT_PATRON_REQUIRED"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandInProgressError("running"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandExecutionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (CommandExecutionError("INVALID_LINE"), 422, "COMMAND_REJECTED"),
    ],
)
def test_financial_draft_creation_maps_service_errors(error, status_code, detail):
    response = _client(draft_service=_FinancialCommandService(error=error)).post(
        f"/api/v1/patron/cases/{uuid4()}/financial-reports/drafts",
        json=_draft_payload(),
        headers=_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (PermissionError("FORBIDDEN"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandInProgressError("running"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandExecutionError("VERSION_CONFLICT"), 409, "VERSION_CONFLICT"),
        (CommandExecutionError("INVALID_LINE"), 422, "COMMAND_REJECTED"),
    ],
)
def test_financial_line_and_publication_map_service_errors(error, status_code, detail):
    client = _client(
        line_service=_FinancialCommandService(error=error),
        publication_service=_FinancialCommandService(error=error),
    )
    line = client.post(
        f"/api/v1/patron/cases/{uuid4()}/financial-reports/{uuid4()}/lines",
        json=_line_payload(),
        headers=_headers(),
    )
    publication = client.post(
        f"/api/v1/patron/cases/{uuid4()}/financial-reports/{uuid4()}/publications",
        json=_publish_payload(),
        headers=_headers(),
    )

    assert line.status_code == status_code
    assert line.json() == {"detail": detail}
    assert publication.status_code == status_code
    assert publication.json() == {"detail": detail}


def test_get_draft_and_published_report_are_no_store_and_financially_complete():
    client = _client()
    case_id = uuid4()
    report_id = uuid4()
    draft = client.get(
        f"/api/v1/patron/cases/{case_id}/financial-reports/{report_id}/draft",
        headers=_headers(),
    )
    published = client.get(
        f"/api/v1/patron/cases/{case_id}/financial-reports/{report_id}",
        headers=_headers(),
    )

    assert draft.status_code == 200
    assert published.status_code == 200
    assert draft.headers["cache-control"] == "no-store"
    assert published.headers["cache-control"] == "no-store"
    assert draft.json()["status"] == "DRAFT"
    assert published.json()["status"] == "PUBLISHED"
    assert draft.json()["summary"]["gross_margin_minor"] == 60000
    assert published.json()["lines"][0]["amount_minor"] == 125000


@pytest.mark.parametrize("method", ["get_draft", "get"])
def test_financial_read_maps_permission_errors(method):
    client = _client(service=_ReportService(error=PermissionError("NOT_FOUND_OR_FORBIDDEN")))
    path = "/draft" if method == "get_draft" else ""
    response = client.get(
        f"/api/v1/patron/cases/{uuid4()}/financial-reports/{uuid4()}{path}",
        headers=_headers(),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "NOT_FOUND_OR_FORBIDDEN"}


def test_financial_payload_rejects_tenant_and_collaborator_fields():
    response = _client().post(
        f"/api/v1/patron/cases/{uuid4()}/financial-reports/drafts",
        json={**_draft_payload(), "tenant_id": str(uuid4()), "assignment_id": str(uuid4())},
        headers=_headers(),
    )

    assert response.status_code == 422
