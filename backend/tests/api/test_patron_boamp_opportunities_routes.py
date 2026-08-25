from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.patron_boamp_opportunities import (
    build_patron_boamp_opportunity_router,
)
from app.modules.opportunity.application.boamp_qualification_errors import (
    BoampQualificationIdempotencyConflict,
)
from app.platform.security.context import ActorKind
from fastapi import FastAPI
from fastapi.testclient import TestClient

TENANT_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddd0001")
ACTOR_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddd0002")
OBSERVATION_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddd0003")


class FakeResolver:
    def __init__(self, context) -> None:
        self.context = context

    def resolve(self, *, access_token: str):
        assert access_token == "token"
        return self.context


class FakePolicy:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed

    def authorize(self, *, context, request):
        return SimpleNamespace(
            allowed=self.allowed,
            http_status_code=200 if self.allowed else 403,
            code="OK" if self.allowed else "FORBIDDEN",
        )


class FakeSession:
    def __init__(self, *values: object) -> None:
        self.values = list(values)

    def scalar(self, _statement):
        return self.values.pop(0)


class SessionFactory:
    def __init__(self, *values: object) -> None:
        self.values = values

    def __call__(self):
        return _SessionContext(FakeSession(*self.values))

    def begin(self):
        return _SessionContext(FakeSession(*self.values))


class _SessionContext:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *_args) -> None:
        return None


def _observation() -> SimpleNamespace:
    return SimpleNamespace(
        id=OBSERVATION_ID,
        source_notice_id="A-1",
        title="Réhabilitation école",
        publication_date=datetime(2026, 8, 20, tzinfo=UTC).date(),
        response_deadline=datetime(2026, 9, 1, 12, tzinfo=UTC),
        department_codes=["59"],
        market_types=["TRAVAUX"],
        source_status="EN_COURS",
        score_version="BOAMP_PUBLIC_V1",
        score=100,
        score_explanation_json={"score": 100},
        fingerprint_sha256="a" * 64,
    )


def _runtime(*values: object, repository: FakeRepository | None = None):
    return SimpleNamespace(
        session_factory=SessionFactory(*values),
        boamp_qualification_repository=repository or FakeRepository(),
    )


class FakeRepository:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def list_observations(self, *, session, tenant_id, limit, min_score):
        return (_observation(),)

    def persist_qualification(self, **_kwargs):
        if self.error is not None:
            raise self.error
        return SimpleNamespace(qualification_id=uuid4(), event_id=uuid4(), replayed=False)


def _client(
    *,
    allowed: bool = True,
    session_values: tuple[object, ...] = (uuid4(),),
    repository: FakeRepository | None = None,
):
    context = SimpleNamespace(
        tenant_id=TENANT_ID,
        actor_id=ACTOR_ID,
        actor_kind=ActorKind.PATRON_ADMIN,
        identity_id=ACTOR_ID,
        membership_id=uuid4(),
        session_id=uuid4(),
        correlation_id=uuid4(),
    )
    app = FastAPI()
    app.include_router(
        build_patron_boamp_opportunity_router(
            runtime=_runtime(*session_values, repository=repository),
            security_runtime=ConsultationSecurityRuntime(
                context_resolver=FakeResolver(context),
                policy=FakePolicy(allowed=allowed),
            ),
        )
    )
    return TestClient(app)


def test_read_route_requires_bearer_and_returns_closed_projection() -> None:
    client = _client()

    unauthenticated = client.get("/api/v1/patron/boamp-opportunities")
    assert unauthenticated.status_code == 401

    response = client.get(
        "/api/v1/patron/boamp-opportunities?min_score=80&limit=10",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    body = response.json()["observations"][0]
    assert body["source_notice_id"] == "A-1"
    assert body["score"] == 100
    assert "tenant_id" not in body
    assert "actor_id" not in body


def test_qualification_route_authorizes_and_returns_receipt() -> None:
    client = _client(session_values=(uuid4(), _observation()))
    response = client.post(
        f"/api/v1/patron/boamp-opportunities/{OBSERVATION_ID}/qualification",
        headers={"Authorization": "Bearer token"},
        json={
            "decision": "QUALIFIED",
            "reason_code": "RELEVANT_PUBLIC_SIGNAL",
            "command_id": str(uuid4()),
            "idempotency_key": str(uuid4()),
        },
    )

    assert response.status_code == 201
    assert set(response.json()) == {"qualification_id", "event_id", "replayed"}


def test_qualification_route_denies_policy_before_write() -> None:
    client = _client(allowed=False)
    response = client.post(
        f"/api/v1/patron/boamp-opportunities/{OBSERVATION_ID}/qualification",
        headers={"Authorization": "Bearer token"},
        json={
            "decision": "QUALIFIED",
            "reason_code": "RELEVANT_PUBLIC_SIGNAL",
            "command_id": str(uuid4()),
            "idempotency_key": str(uuid4()),
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "FORBIDDEN"


def test_qualification_conflict_maps_only_typed_error_to_409() -> None:
    client = _client(
        session_values=(uuid4(), _observation()),
        repository=FakeRepository(error=BoampQualificationIdempotencyConflict("reused")),
    )
    response = client.post(
        f"/api/v1/patron/boamp-opportunities/{OBSERVATION_ID}/qualification",
        headers={"Authorization": "Bearer token"},
        json={
            "decision": "QUALIFIED",
            "reason_code": "RELEVANT_PUBLIC_SIGNAL",
            "command_id": str(uuid4()),
            "idempotency_key": str(uuid4()),
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "IDEMPOTENCY_CONFLICT"}


def test_route_payload_is_closed() -> None:
    client = _client(session_values=(uuid4(), _observation()))
    response = client.post(
        f"/api/v1/patron/boamp-opportunities/{OBSERVATION_ID}/qualification",
        headers={"Authorization": "Bearer token"},
        json={
            "decision": "QUALIFIED",
            "reason_code": "RELEVANT_PUBLIC_SIGNAL",
            "command_id": str(uuid4()),
            "idempotency_key": str(uuid4()),
            "tenant_id": str(TENANT_ID),
        },
    )

    assert response.status_code == 422


def test_case_conversion_is_explicitly_not_configured_without_service() -> None:
    client = _client()

    response = client.post(
        f"/api/v1/patron/boamp-opportunities/{OBSERVATION_ID}/case",
        json={"command_id": str(uuid4()), "idempotency_key": str(uuid4())},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "BOAMP_CASE_CONVERSION_NOT_CONFIGURED"
