from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.patron_enterprise_library import (
    build_patron_enterprise_library_router,
)
from app.modules.enterprise.application.enterprise_upload import (
    EnterpriseUploadAlreadyClaimedError,
    EnterpriseUploadRejectedError,
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


def _runtime(*, resolver_error: Exception | None = None) -> ConsultationSecurityRuntime:
    return ConsultationSecurityRuntime(
        context_resolver=_Resolver(error=resolver_error),
        policy=SimpleNamespace(),
    )


def _client(*, service=None, upload_service=None, resolver_error=None) -> TestClient:
    app = FastAPI()
    app.include_router(
        build_patron_enterprise_library_router(
            service=service or _LibraryService(),
            upload_service=upload_service or _UploadService(),
            security_runtime=_runtime(resolver_error=resolver_error),
        )
    )
    return TestClient(app, raise_server_exceptions=False)


def _result(*, replayed: bool = False, result_code: str = "OK") -> SimpleNamespace:
    aggregate_id = uuid4()
    return SimpleNamespace(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        result_code=result_code,
        aggregate_refs=[{"aggregate_id": str(aggregate_id), "aggregate_revision": 2}],
        event_ids=[str(uuid4())],
        replayed=replayed,
    )


def _company_payload() -> dict[str, object]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "legal_name": "Bâtiments Karim SAS",
        "trade_name": "SMART BÂTIMENT",
        "siren": "123456789",
        "siret": "12345678900011",
        "vat_number": "FR12123456789",
        "address_line1": "12 rue des Métiers",
        "postal_code": "75001",
        "city": "Paris",
        "country_code": "FR",
    }


def _document_payload() -> dict[str, object]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_revision": 2,
        "document_kind": "KBIS",
        "document_label": "Extrait Kbis",
        "storage_object_id": str(uuid4()),
        "original_filename": "kbis.pdf",
        "issued_at": NOW.isoformat(),
        "expires_at": (NOW + timedelta(days=365)).isoformat(),
        "verification_status": "PENDING",
    }


def _prepare_upload_payload() -> dict[str, object]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "document_kind": "KBIS",
        "document_label": "Extrait Kbis",
        "original_filename": "kbis.pdf",
        "expected_byte_size": 8,
        "expires_at": (NOW + timedelta(days=365)).isoformat(),
    }


def _verify_payload() -> dict[str, object]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "expected_verification_revision": 2,
        "outcome": "VALIDATED",
        "reason_code": "DOCUMENT_ACCEPTED",
    }


class _LibraryService:
    def __init__(self, *, error=None, read_error=None):
        self.error = error
        self.read_error = read_error
        self.calls = 0

    def create_company(self, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return _result(replayed=self.calls > 1, result_code="ENTERPRISE_COMPANY_CREATED")

    def register_document(self, **kwargs):
        if self.error is not None:
            raise self.error
        return _result(result_code="ENTERPRISE_DOCUMENT_REGISTERED")

    def read_company(self, **kwargs):
        if self.read_error is not None:
            raise self.read_error
        document = SimpleNamespace(
            document_id=uuid4(),
            document_kind="KBIS",
            document_label="Extrait Kbis",
            issued_at=NOW,
            expires_at=NOW + timedelta(days=365),
            verification_status="VALIDATED",
            verification_revision=3,
        )
        return SimpleNamespace(
            company_id=uuid4(),
            aggregate_revision=3,
            legal_name="Bâtiments Karim SAS",
            trade_name="SMART BÂTIMENT",
            siren="123456789",
            siret="12345678900011",
            vat_number="FR12123456789",
            address_line1="12 rue des Métiers",
            postal_code="75001",
            city="Paris",
            country_code="FR",
            documents=[document],
        )


class _UploadService:
    def __init__(self, *, error=None, target_value=None, verify_error=None):
        self.error = error
        self.target_value = target_value
        self.verify_error = verify_error

    def prepare(self, **kwargs):
        if self.error is not None:
            raise self.error
        return _result(result_code="ENTERPRISE_DOCUMENT_UPLOAD_PREPARED")

    def target(self, **kwargs):
        return self.target_value

    async def upload(self, **kwargs):
        if self.error is not None:
            raise self.error
        return SimpleNamespace(upload_id=kwargs["upload_id"])

    def verify(self, **kwargs):
        if self.verify_error is not None:
            raise self.verify_error
        return _result(result_code="ENTERPRISE_DOCUMENT_VERIFIED")


def _headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


@pytest.mark.parametrize("authorization", [None, "Basic test-token", "Bearer"])
def test_enterprise_library_rejects_missing_or_malformed_bearer(authorization):
    client = _client()
    headers = {} if authorization is None else {"Authorization": authorization}

    response = client.get("/api/v1/patron/enterprise/company", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_enterprise_library_maps_invalid_resolved_context_to_401():
    client = _client(resolver_error=UnauthenticatedError())

    response = client.post(
        "/api/v1/patron/enterprise/company",
        json=_company_payload(),
        headers=_headers(),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_create_company_returns_201_then_200_on_replay():
    service = _LibraryService()
    client = _client(service=service)
    payload = _company_payload()

    first = client.post("/api/v1/patron/enterprise/company", json=payload, headers=_headers())
    replay = client.post("/api/v1/patron/enterprise/company", json=payload, headers=_headers())

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert first.json()["result_code"] == "ENTERPRISE_COMPANY_CREATED"


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("PATRON_REQUIRED"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandInProgressError("running"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandExecutionError("ENTERPRISE_COMPANY_ALREADY_EXISTS"), 409, "COMPANY_ALREADY_EXISTS"),
        (CommandExecutionError("INVALID_COMPANY"), 422, "COMMAND_REJECTED"),
    ],
)
def test_create_company_maps_service_errors(error, status_code, detail):
    client = _client(service=_LibraryService(error=error))

    response = client.post(
        "/api/v1/patron/enterprise/company",
        json=_company_payload(),
        headers=_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (PermissionError("PATRON_REQUIRED"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandInProgressError("running"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandExecutionError("VERSION_CONFLICT"), 409, "VERSION_CONFLICT"),
        (CommandExecutionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (CommandExecutionError("INVALID_DOCUMENT"), 422, "COMMAND_REJECTED"),
    ],
)
def test_register_document_maps_service_errors(error, status_code, detail):
    client = _client(service=_LibraryService(error=error))

    response = client.post(
        f"/api/v1/patron/enterprise/companies/{uuid4()}/documents",
        json=_document_payload(),
        headers=_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_read_company_returns_projection_without_storage_metadata():
    client = _client()

    response = client.get("/api/v1/patron/enterprise/company", headers=_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["legal_name"] == "Bâtiments Karim SAS"
    assert body["documents"][0]["verification_status"] == "VALIDATED"
    assert "storage_object_id" not in body["documents"][0]
    assert "original_filename" not in body["documents"][0]


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [(PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
     (PermissionError("PATRON_REQUIRED"), 403, "FORBIDDEN")],
)
def test_read_company_maps_permission_errors(error, status_code, detail):
    client = _client(service=_LibraryService(read_error=error))

    response = client.get("/api/v1/patron/enterprise/company", headers=_headers())

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("PATRON_REQUIRED"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandInProgressError("running"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandExecutionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (CommandExecutionError("INVALID_UPLOAD"), 422, "COMMAND_REJECTED"),
    ],
)
def test_prepare_upload_maps_service_errors(error, status_code, detail):
    client = _client(upload_service=_UploadService(error=error))

    response = client.post(
        f"/api/v1/patron/enterprise/companies/{uuid4()}/documents/upload",
        json=_prepare_upload_payload(),
        headers=_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_prepare_upload_returns_receipt():
    client = _client()

    response = client.post(
        f"/api/v1/patron/enterprise/companies/{uuid4()}/documents/upload",
        json=_prepare_upload_payload(),
        headers=_headers(),
    )

    assert response.status_code == 201
    assert response.json()["result_code"] == "ENTERPRISE_DOCUMENT_UPLOAD_PREPARED"


@pytest.mark.parametrize(
    ("headers", "status_code", "detail"),
    [({}, 400, "IDEMPOTENCY_KEY_REQUIRED"), ({"Idempotency-Key": "not-a-uuid"}, 422, None)],
)
def test_upload_content_requires_uuid_idempotency_key(headers, status_code, detail):
    upload_id = uuid4()
    company_id = uuid4()
    service = _UploadService(target_value=SimpleNamespace(company_id=company_id))
    client = _client(upload_service=service)
    request_headers = {**_headers(), **headers}

    response = client.put(
        f"/api/v1/patron/enterprise/companies/{company_id}/documents/uploads/{upload_id}/content",
        content=b"document",
        headers=request_headers,
    )

    assert response.status_code == status_code
    if detail is not None:
        assert response.json() == {"detail": detail}


def test_upload_content_rejects_invalid_content_length_and_target_mismatch():
    upload_id = uuid4()
    company_id = uuid4()
    service = _UploadService(target_value=SimpleNamespace(company_id=company_id))
    client = _client(upload_service=service)
    headers = {**_headers(), "Idempotency-Key": str(uuid4()), "Content-Length": "bad"}

    invalid_length = client.put(
        f"/api/v1/patron/enterprise/companies/{company_id}/documents/uploads/{upload_id}/content",
        content=b"document",
        headers=headers,
    )
    mismatch_client = _client(
        upload_service=_UploadService(target_value=SimpleNamespace(company_id=uuid4()))
    )
    mismatch = mismatch_client.put(
        f"/api/v1/patron/enterprise/companies/{company_id}/documents/uploads/{upload_id}/content",
        content=b"document",
        headers={**_headers(), "Idempotency-Key": str(uuid4())},
    )

    assert invalid_length.status_code == 400
    assert invalid_length.json() == {"detail": "INVALID_CONTENT_LENGTH"}
    assert mismatch.status_code == 404
    assert mismatch.json() == {"detail": "NOT_FOUND_OR_FORBIDDEN"}


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("hidden"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (EnterpriseUploadAlreadyClaimedError("claimed"), 409, "UPLOAD_NOT_AWAITING"),
        (EnterpriseUploadRejectedError(status_code=413), 413, "UPLOAD_REJECTED"),
    ],
)
def test_upload_content_maps_upload_errors(error, status_code, detail):
    upload_id = uuid4()
    company_id = uuid4()
    service = _UploadService(
        error=error,
        target_value=SimpleNamespace(company_id=company_id),
    )
    client = _client(upload_service=service)

    response = client.put(
        f"/api/v1/patron/enterprise/companies/{company_id}/documents/uploads/{upload_id}/content",
        content=b"document",
        headers={**_headers(), "Idempotency-Key": str(uuid4())},
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_upload_content_returns_clean_state():
    upload_id = uuid4()
    company_id = uuid4()
    service = _UploadService(target_value=SimpleNamespace(company_id=company_id))
    client = _client(upload_service=service)

    response = client.put(
        f"/api/v1/patron/enterprise/companies/{company_id}/documents/uploads/{upload_id}/content",
        content=b"document",
        headers={**_headers(), "Idempotency-Key": str(uuid4()), "Content-Length": "8"},
    )

    assert response.status_code == 200
    assert response.json() == {"upload_id": str(upload_id), "state": "CLEAN"}


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (PermissionError("PATRON_REQUIRED"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandInProgressError("running"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandExecutionError("VERSION_CONFLICT"), 409, "VERSION_CONFLICT"),
        (CommandExecutionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (CommandExecutionError("INVALID_VERIFICATION"), 422, "COMMAND_REJECTED"),
    ],
)
def test_verify_document_maps_service_errors(error, status_code, detail):
    client = _client(upload_service=_UploadService(verify_error=error))

    response = client.post(
        f"/api/v1/patron/enterprise/companies/{uuid4()}/documents/{uuid4()}/verification",
        json=_verify_payload(),
        headers=_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_verify_document_returns_receipt():
    client = _client()

    response = client.post(
        f"/api/v1/patron/enterprise/companies/{uuid4()}/documents/{uuid4()}/verification",
        json=_verify_payload(),
        headers=_headers(),
    )

    assert response.status_code == 200
    assert response.json()["result_code"] == "ENTERPRISE_DOCUMENT_VERIFIED"
