from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.preparation import (
    build_preparation_review_router,
    build_preparation_router,
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


def _client(*, service=None, review_service=None, resolver_error=None):
    app = FastAPI()
    app.include_router(
        build_preparation_router(
            service=service or _PreparationService(),
            security_runtime=_runtime(resolver_error=resolver_error),
        )
    )
    app.include_router(
        build_preparation_review_router(
            service=review_service or _ReviewService(),
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
                "aggregate_type": "PreparationPackage",
                "aggregate_id": str(uuid4()),
                "aggregate_revision": 2,
            }
        ],
        event_ids=[str(uuid4())],
        replayed=replayed,
    )


def _readiness_payload():
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_revision": 1,
        "package_id": str(uuid4()),
        "assignment_id": str(uuid4()),
        "dce_version_id": str(uuid4()),
    }


def _document_payload():
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_revision": 1,
        "readiness_revision": 2,
        "document_kind": "TECHNICAL_RESPONSE",
    }


def _review_payload():
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_package_revision": 1,
        "review_id": str(uuid4()),
        "target_document_id": str(uuid4()),
        "target_version": 1,
    }


def _decision_payload():
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_review_revision": 1,
        "review_id": str(uuid4()),
        "target_document_id": str(uuid4()),
        "decision_code": "ACCEPTED",
        "decision_note": "Revue terminée.",
    }


def _correction_payload():
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "review_id": str(uuid4()),
        "target_document_id": str(uuid4()),
        "correction_code": "WORDING_UNCLEAR",
        "instruction": "Clarifier la section technique.",
        "source_locator": "section:3",
    }


def _draft_payload():
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_package_revision": 1,
        "draft_id": str(uuid4()),
        "source_document_id": str(uuid4()),
        "section_codes": ["TECH-01"],
        "source_refs": [str(uuid4())],
    }


class _PreparationService:
    def __init__(self, *, error=None, read_error=None):
        self.error = error
        self.read_error = read_error
        self.calls = 0

    def execute(self, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        code = "PREPARATION_READINESS_EVALUATED"
        if kwargs["command"].__class__.__name__ == "GenerateTechnicalDocumentCommand":
            code = (
                "CONTROLLED_DRAFT_GENERATED"
                if kwargs["command"].document_kind in {"DC1", "DC2", "DC4"}
                else "TECHNICAL_DOCUMENT_GENERATED"
            )
        return _result(code=code, replayed=self.calls > 1)

    def read_package(self, **kwargs):
        if self.read_error is not None:
            raise self.read_error
        readiness = SimpleNamespace(
            id=uuid4(),
            revision=2,
            state="READY_WITH_WARNINGS",
            blocker_codes_json=[],
            warning_codes_json=["OPTIONAL_REFERENCE"],
            checked_requirement_count=4,
            checked_task_count=7,
        )
        document = SimpleNamespace(
            id=uuid4(),
            version=1,
            document_kind="TECHNICAL_RESPONSE",
            state="GENERATED",
            readiness_id=readiness.id,
        )
        package = SimpleNamespace(
            id=kwargs["package_id"],
            case_id=uuid4(),
            assignment_id=uuid4(),
            dce_version_id=uuid4(),
            state="GENERATED",
            aggregate_revision=3,
        )
        return package, readiness, [document]


class _ReviewService:
    def __init__(self, *, error=None):
        self.error = error
        self.calls = 0

    def execute(self, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        name = kwargs["command"].__class__.__name__
        code = {
            "RequestPreparationReviewCommand": "PREPARATION_REVIEW_REQUESTED",
            "DecidePreparationReviewCommand": "PREPARATION_REVIEW_DECIDED",
            "AddPreparationCorrectionCommand": "PREPARATION_CORRECTION_ADDED",
            "CreateTechnicalResponseDraftCommand": "TECHNICAL_RESPONSE_DRAFT_CREATED",
        }[name]
        return _result(code=code, replayed=self.calls > 1)


def _headers():
    return {"Authorization": "Bearer test-token"}


@pytest.mark.parametrize("authorization", [None, "Basic test-token", "Bearer"])
def test_preparation_routes_reject_missing_or_malformed_bearer(authorization):
    client = _client()
    headers = {} if authorization is None else {"Authorization": authorization}

    response = client.get(f"/api/v1/collaborator/preparation/{uuid4()}", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_preparation_routes_map_invalid_context_to_401():
    response = _client(resolver_error=UnauthenticatedError()).post(
        f"/api/v1/collaborator/cases/{uuid4()}/preparation/readiness",
        json=_readiness_payload(),
        headers=_headers(),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_read_package_returns_readiness_and_document_revision():
    package_id = uuid4()
    response = _client().get(
        f"/api/v1/collaborator/preparation/{package_id}", headers=_headers()
    )

    assert response.status_code == 200
    body = response.json()
    assert body["package_id"] == str(package_id)
    assert body["latest_readiness"]["state"] == "READY_WITH_WARNINGS"
    assert body["generated_documents"][0]["readiness_revision"] == 2


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [(PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
     (PermissionError("ASSIGNMENT_REQUIRED"), 403, "FORBIDDEN")],
)
def test_read_package_maps_service_errors(error, status_code, detail):
    response = _client(service=_PreparationService(read_error=error)).get(
        f"/api/v1/collaborator/preparation/{uuid4()}", headers=_headers()
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_readiness_and_document_generation_return_201_then_200_on_replay():
    service = _PreparationService()
    client = _client(service=service)
    case_id = uuid4()
    readiness = client.post(
        f"/api/v1/collaborator/cases/{case_id}/preparation/readiness",
        json=_readiness_payload(),
        headers=_headers(),
    )
    document = client.post(
        f"/api/v1/collaborator/preparation/{uuid4()}/documents",
        json=_document_payload(),
        headers=_headers(),
    )

    assert readiness.status_code == 201
    assert document.status_code == 200
    assert readiness.json()["result_code"] == "PREPARATION_READINESS_EVALUATED"
    assert document.json()["result_code"] == "TECHNICAL_DOCUMENT_GENERATED"


@pytest.mark.parametrize("document_kind", ["DC1", "DC2", "DC4"])
def test_controlled_document_routes_accept_only_supported_kinds(document_kind):
    payload = {**_document_payload(), "document_kind": document_kind}
    response = _client(service=_PreparationService()).post(
        f"/api/v1/collaborator/preparation/{uuid4()}/documents",
        json=payload,
        headers=_headers(),
    )

    assert response.status_code == 201
    assert response.json()["result_code"] == "CONTROLLED_DRAFT_GENERATED"


def test_controlled_document_route_rejects_unknown_kind():
    payload = {**_document_payload(), "document_kind": "DC3"}
    response = _client(service=_PreparationService()).post(
        f"/api/v1/collaborator/preparation/{uuid4()}/documents",
        json=payload,
        headers=_headers(),
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (PermissionError("FORBIDDEN"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_KEY_REUSED"),
        (CommandInProgressError("running"), 409, "COMMAND_IN_PROGRESS"),
        (CommandExecutionError("PREPARATION_BLOCKED"), 422, "PREPARATION_BLOCKED"),
    ],
)
def test_preparation_dispatch_maps_service_errors(error, status_code, detail):
    response = _client(service=_PreparationService(error=error)).post(
        f"/api/v1/collaborator/cases/{uuid4()}/preparation/readiness",
        json=_readiness_payload(),
        headers=_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_review_routes_return_each_command_result():
    service = _ReviewService()
    client = _client(review_service=service)
    package_id = uuid4()
    review_id = uuid4()
    paths = [
        (
            f"/api/v1/preparation/{package_id}/reviews",
            _review_payload(),
            "PREPARATION_REVIEW_REQUESTED",
        ),
        (
            f"/api/v1/preparation/{package_id}/reviews/{review_id}/decision",
            _decision_payload(),
            "PREPARATION_REVIEW_DECIDED",
        ),
        (
            f"/api/v1/preparation/{package_id}/reviews/{review_id}/corrections",
            _correction_payload(),
            "PREPARATION_CORRECTION_ADDED",
        ),
        (
            f"/api/v1/preparation/{package_id}/response-drafts",
            _draft_payload(),
            "TECHNICAL_RESPONSE_DRAFT_CREATED",
        ),
    ]

    for index, (path, payload, code) in enumerate(paths):
        response = client.post(path, json=payload, headers=_headers())
        assert response.status_code == (201 if index == 0 else 200)
        assert response.json()["result_code"] == code


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (PermissionError("PATRON_REQUIRED"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_KEY_REUSED"),
        (CommandInProgressError("running"), 409, "COMMAND_IN_PROGRESS"),
        (CommandExecutionError("VERSION_CONFLICT"), 409, "VERSION_CONFLICT"),
        (CommandExecutionError("CORRECTIONS_NOT_REQUESTED"), 422, "CORRECTIONS_NOT_REQUESTED"),
    ],
)
def test_review_dispatch_maps_service_errors(error, status_code, detail):
    response = _client(review_service=_ReviewService(error=error)).post(
        f"/api/v1/preparation/{uuid4()}/reviews",
        json=_review_payload(),
        headers=_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_preparation_payload_rejects_financial_fields():
    response = _client().post(
        f"/api/v1/collaborator/cases/{uuid4()}/preparation/readiness",
        json={**_readiness_payload(), "gross_margin_minor": 100},
        headers=_headers(),
    )

    assert response.status_code == 422
