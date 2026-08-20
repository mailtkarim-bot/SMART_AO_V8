from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.preparation_transmission import (
    build_preparation_transmission_router,
)
from app.platform.events.dispatcher import (
    CommandExecutionError,
    CommandInProgressError,
    IdempotencyKeyReusedError,
)
from app.platform.security.authenticated_context import UnauthenticatedError
from fastapi import FastAPI
from fastapi.testclient import TestClient


@dataclass
class Resolver:
    error: Exception | None = None

    def resolve(self, *, access_token: str):
        if access_token != "test-token" or self.error is not None:
            if self.error is not None:
                raise self.error
            raise UnauthenticatedError()
        return SimpleNamespace(tenant_id=uuid4())


def _runtime(*, error: Exception | None = None) -> ConsultationSecurityRuntime:
    return ConsultationSecurityRuntime(
        context_resolver=Resolver(error=error),
        policy=SimpleNamespace(),
    )


def _result(*, replayed: bool = False):
    return SimpleNamespace(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        result_code="PREPARATION_SNAPSHOT_CREATED",
        aggregate_refs=[
            {
                "aggregate_type": "PreparationSnapshot",
                "aggregate_id": str(uuid4()),
                "aggregate_revision": 1,
            }
        ],
        event_ids=[uuid4()],
        replayed=replayed,
    )


def _client(service, *, resolver_error: Exception | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(
        build_preparation_transmission_router(
            service=service,
            security_runtime=_runtime(error=resolver_error),
        )
    )
    return TestClient(app, raise_server_exceptions=False)


def _snapshot_payload(package_id) -> dict[str, object]:
    return {
        "command_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "package_id": str(package_id),
        "snapshot_id": str(uuid4()),
        "expected_package_revision": 3,
    }


class Service:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    def execute(self, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return _result(replayed=self.calls > 1)


@pytest.mark.parametrize("authorization", [None, "Basic test-token", "Bearer"])
def test_transmission_routes_reject_missing_or_malformed_bearer(authorization) -> None:
    client = _client(Service())
    package_id = uuid4()
    headers = {} if authorization is None else {"Authorization": authorization}

    response = client.post(
        f"/api/v1/collaborator/preparation/{package_id}/snapshots",
        json=_snapshot_payload(package_id),
        headers=headers,
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_transmission_route_maps_resolver_failure_to_401() -> None:
    client = _client(Service(), resolver_error=UnauthenticatedError())
    package_id = uuid4()

    response = client.post(
        f"/api/v1/collaborator/preparation/{package_id}/snapshots",
        json=_snapshot_payload(package_id),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_transmission_route_rejects_path_body_mismatch_before_authentication() -> None:
    service = Service()
    client = _client(service)
    path_package_id = uuid4()

    response = client.post(
        f"/api/v1/collaborator/preparation/{path_package_id}/snapshots",
        json=_snapshot_payload(uuid4()),
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "PREPARATION_CONTEXT_MISMATCH"}
    assert service.calls == 0


def test_create_snapshot_route_returns_201_then_200_on_replay() -> None:
    service = Service()
    client = _client(service)
    package_id = uuid4()
    payload = _snapshot_payload(package_id)
    headers = {"Authorization": "Bearer test-token"}

    first = client.post(
        f"/api/v1/collaborator/preparation/{package_id}/snapshots",
        json=payload,
        headers=headers,
    )
    replay = client.post(
        f"/api/v1/collaborator/preparation/{package_id}/snapshots",
        json=payload,
        headers=headers,
    )

    assert first.status_code == 201
    assert first.json()["result_code"] == "PREPARATION_SNAPSHOT_CREATED"
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
        (PermissionError("PATRON_REQUIRED"), 403, "FORBIDDEN"),
        (IdempotencyKeyReusedError("reused"), 409, "IDEMPOTENCY_KEY_REUSED"),
        (CommandInProgressError("running"), 409, "COMMAND_IN_PROGRESS"),
        (CommandExecutionError("VERSION_CONFLICT"), 409, "VERSION_CONFLICT"),
        (
            CommandExecutionError("SNAPSHOT_NOT_FOUND_OR_FORBIDDEN"),
            422,
            "SNAPSHOT_NOT_FOUND_OR_FORBIDDEN",
        ),
    ],
)
def test_transmission_route_maps_service_errors(error, status_code, detail) -> None:
    client = _client(Service(error=error))
    package_id = uuid4()

    response = client.post(
        f"/api/v1/collaborator/preparation/{package_id}/snapshots",
        json=_snapshot_payload(package_id),
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_transmit_snapshot_route_accepts_valid_contract() -> None:
    service = Service()
    client = _client(service)
    package_id = uuid4()
    payload = _snapshot_payload(package_id)
    payload["transmission_id"] = str(uuid4())

    response = client.post(
        f"/api/v1/collaborator/preparation/{package_id}/transmissions",
        json=payload,
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 201
    assert service.calls == 1
