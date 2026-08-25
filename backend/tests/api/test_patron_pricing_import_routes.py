from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.patron_pricing_import import (
    build_patron_pricing_import_router,
)
from app.platform.events.dispatcher import CommandExecutionError, IdempotencyKeyReusedError
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


def _client(
    *,
    service=None,
    commit_service=None,
    creation_service=None,
    read_service=None,
    resolver_error=None,
):
    app = FastAPI()
    app.include_router(
        build_patron_pricing_import_router(
            service=service or _PreviewService(),
            commit_service=commit_service,
            creation_service=creation_service,
            read_service=read_service,
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
            total_minor=125000, truncated=False, limit_reason=None,
            rows=[
                _Row(1, "A-1", "Ouvrage", "U", "10", 12500, 125000, []),
                _Row(2, None, "Ligne invalide", None, None, None, None, ["CODE_REQUIRED"]),
            ],
        )


class _ReadService:
    def __init__(self, *, error=None):
        self.error = error
        self.calls = []

    def get(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            batch_id=kwargs["batch_id"],
            case_id=kwargs["case_id"],
            document_kind="DPGF",
            state="PREVIEWED",
            aggregate_revision=1,
            row_count=2,
            valid_row_count=1,
            error_count=1,
            total_minor=12500,
            rows=[
                _Row(2, "A-1", "Ouvrage", "U", "10", 1250, 12500, []),
                _Row(3, None, None, None, None, None, None, ["DESIGNATION_REQUIRED"]),
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


def test_pricing_import_preview_rejects_oversized_upload_before_service():
    from app.modules.pricing.application.import_preview import MAX_UPLOAD_BYTES

    service = _PreviewService()
    oversized = b"x" * (MAX_UPLOAD_BYTES + 1)
    response = _client(service=service).post(
        f"/api/v1/patron/cases/{uuid4()}/pricing-import/preview",
        files={"upload": ("dpgf.csv", oversized, "text/csv")},
        headers=_headers(),
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "pricing_import_too_large"
    assert service.calls == []


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
      "NOT_FOUND_OR_FORBIDDEN"),
     (CommandExecutionError("FINANCIAL_REPORT_NOT_FOUND_OR_FORBIDDEN"), 404,
      "NOT_FOUND_OR_FORBIDDEN"),
     (CommandExecutionError("VERSION_CONFLICT"), 409, "CONFLICT"),
     (CommandExecutionError("IMPORT_ALREADY_COMMITTED"), 409, "CONFLICT"),
     (CommandExecutionError("INVALID_ROW"), 422, "COMMAND_REJECTED")],
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


class _CreationService:
    def __init__(self, *, error=None, replayed=False):
        self.error = error
        self.replayed = replayed
        self.calls = []
        self.batch_id = uuid4()

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        command = kwargs["command"]
        return SimpleNamespace(
            status="SUCCEEDED",
            command_id=str(command.command_id),
            idempotency_key=str(command.idempotency_key),
            result_code="PRICING_IMPORT_PREVIEWED",
            aggregate_refs=[
                {
                    "aggregate_type": "PricingImportBatch",
                    "aggregate_id": str(self.batch_id),
                    "aggregate_revision": 1,
                }
            ],
            event_ids=[str(uuid4())],
            replayed=self.replayed,
        )


def _creation_headers():
    return {
        **_headers(),
        "X-Command-Id": str(uuid4()),
        "Idempotency-Key": str(uuid4()),
        "X-Correlation-Id": str(uuid4()),
    }


def test_pricing_import_preview_persists_normalized_rows_with_server_hash():
    import hashlib

    creation_service = _CreationService()
    payload = b"normalized-preview-source"
    client = _client(creation_service=creation_service)
    response = client.post(
        f"/api/v1/patron/cases/{uuid4()}/pricing-import/preview?document_kind=DPGF",
        files={
            "upload": (
                "dpgf.xlsx",
                payload,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=_creation_headers(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["batch_id"] == str(creation_service.batch_id)
    assert body["state"] == "PREVIEWED"
    assert body["result_code"] == "PRICING_IMPORT_PREVIEWED"
    assert body["replayed"] is False
    assert "source_sha256" not in body
    assert creation_service.calls[0]["command"].source_sha256 == hashlib.sha256(payload).hexdigest()
    assert str(creation_service.calls[0]["command"].case_id) == response.json()["case_id"]


def test_pricing_import_preview_replay_returns_200_and_replayed_receipt():
    creation_service = _CreationService(replayed=True)
    response = _client(creation_service=creation_service).post(
        f"/api/v1/patron/cases/{uuid4()}/pricing-import/preview",
        files={"upload": ("pricing.xlsx", b"source", "application/octet-stream")},
        headers=_creation_headers(),
    )

    assert response.status_code == 200
    assert response.json()["replayed"] is True


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("FORBIDDEN"), 403, "FORBIDDEN"),
        (CommandExecutionError("IDEMPOTENCY_KEY_REUSED"), 409, "IDEMPOTENCY_CONFLICT"),
        (CommandExecutionError("IMPORT_ROWS_INVALID"), 422, "COMMAND_REJECTED"),
    ],
)
def test_pricing_import_preview_creation_maps_service_errors(error, status_code, detail):
    response = _client(creation_service=_CreationService(error=error)).post(
        f"/api/v1/patron/cases/{uuid4()}/pricing-import/preview",
        files={"upload": ("pricing.xlsx", b"source", "application/octet-stream")},
        headers=_creation_headers(),
    )
    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_pricing_import_preview_requires_command_metadata_when_persistence_is_enabled():
    response = _client(creation_service=_CreationService()).post(
        f"/api/v1/patron/cases/{uuid4()}/pricing-import/preview",
        files={"upload": ("pricing.xlsx", b"source", "application/octet-stream")},
        headers=_headers(),
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "COMMAND_METADATA_REQUIRED"}


class _StatefulIdempotentCreationService(_CreationService):
    def __init__(self):
        super().__init__()
        self._source_by_key = {}
        self._receipt_by_key = {}

    def create(self, **kwargs):
        command = kwargs["command"]
        key = command.idempotency_key
        previous_source = self._source_by_key.get(key)
        if previous_source is not None:
            if previous_source != command.source_sha256:
                raise IdempotencyKeyReusedError("IDEMPOTENCY_KEY_REUSED")
            previous = self._receipt_by_key[key]
            return SimpleNamespace(**{**previous.__dict__, "replayed": True})

        receipt = super().create(**kwargs)
        self._source_by_key[key] = command.source_sha256
        self._receipt_by_key[key] = receipt
        return receipt


def test_pricing_import_preview_same_http_command_replays_without_new_batch():
    creation_service = _StatefulIdempotentCreationService()
    headers = _creation_headers()
    case_id = uuid4()
    files = {"upload": ("pricing.xlsx", b"same-source", "application/octet-stream")}
    client = _client(creation_service=creation_service)

    first = client.post(
        f"/api/v1/patron/cases/{case_id}/pricing-import/preview",
        files=files,
        headers=headers,
    )
    replay = client.post(
        f"/api/v1/patron/cases/{case_id}/pricing-import/preview",
        files=files,
        headers=headers,
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert first.json()["batch_id"] == replay.json()["batch_id"]
    assert replay.json()["replayed"] is True
    assert len(creation_service._receipt_by_key) == 1


def test_pricing_import_preview_reused_key_with_changed_source_returns_409():
    creation_service = _StatefulIdempotentCreationService()
    headers = _creation_headers()
    case_id = uuid4()
    client = _client(creation_service=creation_service)

    first = client.post(
        f"/api/v1/patron/cases/{case_id}/pricing-import/preview",
        files={"upload": ("pricing.xlsx", b"source-a", "application/octet-stream")},
        headers=headers,
    )
    conflict = client.post(
        f"/api/v1/patron/cases/{case_id}/pricing-import/preview",
        files={"upload": ("pricing.xlsx", b"source-b", "application/octet-stream")},
        headers=headers,
    )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "IDEMPOTENCY_CONFLICT"}
    assert len(creation_service._receipt_by_key) == 1



def test_pricing_import_read_returns_private_normalized_projection():
    read_service = _ReadService()
    case_id = uuid4()
    batch_id = uuid4()
    response = _client(read_service=read_service).get(
        f"/api/v1/patron/cases/{case_id}/pricing-import/{batch_id}",
        headers=_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["batch_id"] == str(batch_id)
    assert body["case_id"] == str(case_id)
    assert body["state"] == "PREVIEWED"
    assert body["rows"][0]["total_minor"] == 12500
    assert body["rows"][1]["errors"] == ["DESIGNATION_REQUIRED"]
    assert "source_sha256" not in body
    assert "filename" not in body
    assert read_service.calls[0]["batch_id"] == batch_id


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (PermissionError("FORBIDDEN"), 403, "FORBIDDEN"),
    ],
)
def test_pricing_import_read_maps_private_access_errors(error, status_code, detail):
    response = _client(read_service=_ReadService(error=error)).get(
        f"/api/v1/patron/cases/{uuid4()}/pricing-import/{uuid4()}",
        headers=_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_pricing_import_commit_maps_idempotency_key_reuse_to_409():
    response = _client(
        commit_service=_CommitService(
            error=IdempotencyKeyReusedError("IDEMPOTENCY_KEY_REUSED")
        )
    ).post(
        f"/api/v1/patron/cases/{uuid4()}/pricing-import/{uuid4()}/commit",
        json=_commit_payload(),
        headers=_headers(),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "CONFLICT"}
