from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.patron_opportunity_watch_profiles import (
    build_patron_opportunity_watch_profile_router,
)
from app.modules.opportunity.application.patron_watch_profile import (
    WatchProfileProjection,
    WatchProfileVersionProjection,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient

TENANT_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccc0001")
PROFILE_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccc0002")
VERSION_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccc0003")
COMMAND_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccc0004")
IDEMPOTENCY_KEY = UUID("cccccccc-cccc-cccc-cccc-cccccccc0005")


class FakeResolver:
    def __init__(self, context) -> None:
        self.context = context

    def resolve(self, *, access_token: str):
        assert access_token == "token"
        return self.context


class FakeProfileService:
    def __init__(self) -> None:
        self.replayed = False
        self.denied = False

    def create(self, *, actor, command, now):
        if self.denied:
            raise PermissionError("OPPORTUNITY_PROFILE_PATRON_REQUIRED")
        return SimpleNamespace(
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            result_code="OPPORTUNITY_PROFILE_CREATED",
            aggregate_refs=[],
            event_ids=[],
            replayed=self.replayed,
        )

    def add_version(self, *, actor, command, now):
        return SimpleNamespace(
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            result_code="OPPORTUNITY_PROFILE_VERSION_ADDED",
            aggregate_refs=[],
            event_ids=[],
            replayed=False,
        )

    def read(self, *, actor, profile_id, now):
        return _projection()

    def read_all(self, *, actor, now):
        return (_projection(),)


def _client(service: FakeProfileService) -> TestClient:
    context = SimpleNamespace(tenant_id=TENANT_ID)
    app = FastAPI()
    app.include_router(
        build_patron_opportunity_watch_profile_router(
            service=service,
            security_runtime=ConsultationSecurityRuntime(
                context_resolver=FakeResolver(context),
                policy=SimpleNamespace(),
            ),
        )
    )
    return TestClient(app)


def _create_payload() -> dict[str, object]:
    return {
        "command_id": str(COMMAND_ID),
        "idempotency_key": str(IDEMPOTENCY_KEY),
        "name": "Gros œuvre",
        "keywords": ["réhabilitation"],
        "project_types": ["REFURBISHMENT"],
        "included_departments": ["59"],
    }


def test_profile_routes_require_bearer() -> None:
    response = _client(FakeProfileService()).get(
        "/api/v1/patron/opportunity-watch-profiles"
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "UNAUTHENTICATED"


def test_create_profile_returns_201_then_200_on_replay() -> None:
    service = FakeProfileService()
    client = _client(service)

    first = client.post(
        "/api/v1/patron/opportunity-watch-profiles",
        headers={"Authorization": "Bearer token"},
        json=_create_payload(),
    )
    service.replayed = True
    replay = client.post(
        "/api/v1/patron/opportunity-watch-profiles",
        headers={"Authorization": "Bearer token"},
        json=_create_payload(),
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["result_code"] == "OPPORTUNITY_PROFILE_CREATED"
    assert "profile_id" not in _create_payload()


def test_add_version_and_read_projection_do_not_expose_server_context() -> None:
    client = _client(FakeProfileService())
    version_response = client.post(
        f"/api/v1/patron/opportunity-watch-profiles/{PROFILE_ID}/versions",
        headers={"Authorization": "Bearer token"},
        json={
            "command_id": str(uuid4()),
            "idempotency_key": str(uuid4()),
            "version_id": str(VERSION_ID),
            "expected_revision": 0,
            "keywords": ["construction"],
        },
    )
    read_response = client.get(
        f"/api/v1/patron/opportunity-watch-profiles/{PROFILE_ID}",
        headers={"Authorization": "Bearer token"},
    )

    assert version_response.status_code == 201
    assert read_response.status_code == 200
    body = read_response.json()
    assert body["profile_id"] == str(PROFILE_ID)
    assert body["versions"][0]["criteria"]["keywords"] == ["construction"]
    assert "tenant_id" not in body
    assert "actor_id" not in body
    assert "command_id" not in body


def test_profile_route_maps_non_patron_to_forbidden() -> None:
    service = FakeProfileService()
    service.denied = True
    response = _client(service).post(
        "/api/v1/patron/opportunity-watch-profiles",
        headers={"Authorization": "Bearer token"},
        json=_create_payload(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "FORBIDDEN"


def test_profile_payload_is_closed() -> None:
    payload = _create_payload()
    payload["tenant_id"] = str(TENANT_ID)

    response = _client(FakeProfileService()).post(
        "/api/v1/patron/opportunity-watch-profiles",
        headers={"Authorization": "Bearer token"},
        json=payload,
    )

    assert response.status_code == 422


def _projection() -> WatchProfileProjection:
    return WatchProfileProjection(
        profile_id=PROFILE_ID,
        aggregate_revision=0,
        current_version=1,
        state="ACTIVE",
        versions=(
            WatchProfileVersionProjection(
                version_id=PROFILE_ID,
                version_number=1,
                name="Gros œuvre",
                criteria={"keywords": ["construction"]},
                criteria_sha256="a" * 64,
            ),
        ),
    )
